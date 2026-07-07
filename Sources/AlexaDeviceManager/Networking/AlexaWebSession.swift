import Foundation
import WebKit

enum AlexaSessionError: LocalizedError {
    case invalidResponse
    case httpError(Int)
    case graphQLErrors([String])

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from the server."
        case .httpError(let code):
            return "HTTP error \(code) – maybe not logged in or wrong region."
        case .graphQLErrors(let messages):
            return "GraphQL error: \(messages.joined(separator: ", "))"
        }
    }
}

/// Runs all Amazon requests as `fetch()` calls *inside* the loaded WKWebView
/// page (via `evaluateJavaScript`), not through a separate URLSession. This
/// matches exactly the tested browser-console method from NOTES.md #4 -
/// cookies, origin, and all browser headers are automatically correct this
/// way, without having to manually copy cookies into a URLSession (which
/// could fail on httpOnly/SameSite cookies).
@MainActor
final class AlexaWebSession: NSObject, ObservableObject {
    @Published var region: AlexaRegion = AlexaRegion.candidates[0]
    @Published var isLoggedIn = false
    @Published var isLoading = false
    @Published var lastError: String?
    @Published var currentURL: String?
    /// Some accounts additionally need a csrf header for deletion, per NOTES.md.
    @Published var csrfToken: String = ""

    let webView: WKWebView
    /// Whether the login status should be checked automatically after the
    /// next page load. The Alexa API naturally doesn't exist on Amazon's
    /// main domain (step 1) (404) - the check only makes sense after step 2.
    private var shouldCheckLoginOnNextLoad = false
    private var navigationContinuation: CheckedContinuation<Void, Never>?

    override init() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        webView = WKWebView(frame: .zero, configuration: config)
        super.init()
        webView.navigationDelegate = self
    }

    /// Step 1: sign in on Amazon's main domain (email/password/2FA). The
    /// Alexa subdomain itself now only shows a QR code splash screen.
    func loadSignInPage() {
        isLoading = true
        lastError = nil
        shouldCheckLoginOnNextLoad = false
        webView.load(URLRequest(url: region.signInURL))
    }

    /// Step 2: switch to the Alexa subdomain after signing in on the main
    /// domain - the session cookie is valid there too (same root domain).
    func loadAlexaHost() {
        isLoading = true
        lastError = nil
        shouldCheckLoginOnNextLoad = true
        webView.load(URLRequest(url: region.baseURL))
    }

    /// Loads the Alexa host in the background (without a dialog needing to
    /// be visible) and checks whether the Amazon session cookies persisted
    /// from previous launches are still valid. Returns `true` if a valid
    /// login was detected this way.
    @discardableResult
    func attemptAutoLogin() async -> Bool {
        await withCheckedContinuation { continuation in
            navigationContinuation = continuation
            shouldCheckLoginOnNextLoad = true
            isLoading = true
            lastError = nil
            webView.load(URLRequest(url: region.baseURL))
        }
        return isLoggedIn
    }

    private func resumePendingNavigation() {
        navigationContinuation?.resume()
        navigationContinuation = nil
    }

    func checkLoginStatus() async {
        do {
            _ = try await fetchDevices()
            isLoggedIn = true
            lastError = nil
        } catch {
            isLoggedIn = false
            lastError = error.localizedDescription
        }
    }

    // MARK: - JS bridge

    /// Runs `script` as the body of an async function. Unlike
    /// `evaluateJavaScript`, `callAsyncJavaScript` correctly resolves the
    /// returned Promise - an `async () => {...}` IIFE via
    /// `evaluateJavaScript` instead returns a Promise object that WKWebView
    /// can't serialize ("unsupported type").
    private func evaluate(_ script: String) async throws -> String {
        let result = try await webView.callAsyncJavaScript(
            script,
            arguments: [:],
            in: nil,
            contentWorld: .page
        )
        guard let string = result as? String else {
            throw AlexaSessionError.invalidResponse
        }
        return string
    }

    private struct StatusEnvelope: Decodable {
        let status: Int
        let body: String?
    }

    /// Runs an arbitrary GraphQL query and returns the raw body as a String
    /// - only for targeted debugging/research, not for production code.
    func debugRawQuery(_ query: String) async throws -> String {
        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )
        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)
        return String(data: bodyData, encoding: .utf8) ?? "<could not decode body as UTF-8>"
    }

    // MARK: - Listing devices

    /// Loads all devices. Instead of querying a fixed, hand-curated field
    /// list, the app first uses GraphQL introspection to determine ALL
    /// scalar fields of the Endpoint type and queries them directly -
    /// anything beyond that ends up in `Device.rawFields` and is shown in
    /// the "All Fields" column (see `DeviceListView`).
    func fetchDevices() async throws -> [Device] {
        // Only query fields that introspection actually confirmed on THIS
        // account/region - a top-level `connectivity` field does NOT exist
        // on this endpoint type (confirmed via validation error); the
        // online/offline status instead lives in `features` (the feature
        // with `name: "connectivity"`, whose `properties` contains a
        // `reachabilityStatusValue: OK|UNREACHABLE` when
        // `__typename: "Reachability"`, confirmed via live testing, see the
        // alexa_graphql_schema memory). "manufacturer" and
        // "displayCategories" are object fields and need a sub-selection
        // (determined via introspection: manufacturer.value.text,
        // displayCategories.primary.value).
        let discovered = try? await introspectFields()
        let fieldNames = Set(discovered?.fields.map(\.name) ?? [])
        let extraFields = discovered?.fields.filter(Self.isLeafField).map(\.name) ?? []
        do {
            return try await fetchDevices(
                extraFieldNames: extraFields,
                includeFeatures: fieldNames.contains("features"),
                includeManufacturer: fieldNames.contains("manufacturer"),
                includeDisplayCategories: fieldNames.contains("displayCategories"),
                includeAssociatedUnits: fieldNames.contains("associatedUnits")
            )
        } catch AlexaSessionError.graphQLErrors {
            // Fall back to the minimal base query guaranteed to work per
            // NOTES.md #1, in case the extended field list is rejected for
            // some reason.
            return try await fetchDevices(extraFieldNames: [], includeFeatures: false, includeManufacturer: false, includeDisplayCategories: false, includeAssociatedUnits: false)
        }
    }

    private static let knownFieldNames: Set<String> = ["friendlyName", "legacyAppliance", "features", "manufacturer", "displayCategories", "associatedUnits", "id"]

    private func fetchDevices(
        extraFieldNames: [String],
        includeFeatures: Bool,
        includeManufacturer: Bool,
        includeDisplayCategories: Bool,
        includeAssociatedUnits: Bool
    ) async throws -> [Device] {
        var baseFields = ["id", "friendlyName", "legacyAppliance { applianceId }"]
        if includeFeatures {
            baseFields.append("features { name properties { __typename ... on Reachability { reachabilityStatusValue } } }")
        }
        if includeManufacturer {
            baseFields.append("manufacturer { value { text } }")
        }
        if includeDisplayCategories {
            baseFields.append("displayCategories { primary { value } }")
        }
        if includeAssociatedUnits {
            // Introspection shows Unit only has one field: id (no name) -
            // used to link devices to zone/room pseudo-endpoints, which are
            // themselves identified by their own `id`.
            baseFields.append("associatedUnits { id }")
        }
        let extra = extraFieldNames.filter { !Self.knownFieldNames.contains($0) }
        let selection = (baseFields + extra).joined(separator: " ")
        let query = "query { endpoints { items { \(selection) } } }"

        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )

        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)

        guard let json = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] else {
            throw AlexaSessionError.invalidResponse
        }
        if let dataDict = json["data"] as? [String: Any],
           let endpoints = dataDict["endpoints"] as? [String: Any],
           let items = endpoints["items"] as? [[String: Any]] {
            return items.map(Self.parseDevice(from:))
        }
        let errors = (json["errors"] as? [[String: Any]])?.compactMap { $0["message"] as? String }
        throw AlexaSessionError.graphQLErrors(errors ?? ["Unknown GraphQL error"])
    }

    // MARK: - Listing groups

    /// `listDeviceGroups` + the structure of `DeviceGroup`/
    /// `ListDeviceGroupsInput` verified via introspection (see the
    /// alexa_graphql_schema memory). `devicesPaginationParams:
    /// {disablePagination: true}` is required, otherwise `memberDevices.items`
    /// comes back empty (the server default appears to be 0 items per page,
    /// confirmed via live testing).
    func fetchDeviceGroups() async throws -> [DeviceGroup] {
        let query = """
        query { listDeviceGroups(listDeviceGroupsInput: {devicesPaginationParams: {disablePagination: true}}) { deviceGroups { \
        id friendlyName { value { text } } \
        memberDevices { items { id } } \
        } } }
        """
        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )

        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)

        guard let json = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] else {
            throw AlexaSessionError.invalidResponse
        }
        if let dataDict = json["data"] as? [String: Any],
           let listResponse = dataDict["listDeviceGroups"] as? [String: Any],
           let groups = listResponse["deviceGroups"] as? [[String: Any]] {
            return groups.map(Self.parseDeviceGroup(from:))
        }
        let errors = (json["errors"] as? [[String: Any]])?.compactMap { $0["message"] as? String }
        throw AlexaSessionError.graphQLErrors(errors ?? ["Unknown GraphQL error"])
    }

    private static func parseDeviceGroup(from item: [String: Any]) -> DeviceGroup {
        let id = item["id"] as? String ?? ""
        let name = ((item["friendlyName"] as? [String: Any])?["value"] as? [String: Any])?["text"] as? String ?? id
        let memberItems = (item["memberDevices"] as? [String: Any])?["items"] as? [[String: Any]] ?? []
        let endpointIds = memberItems.compactMap { $0["id"] as? String }
        return DeviceGroup(id: id, name: name, memberEndpointIds: Set(endpointIds))
    }

    // MARK: - Managing groups

    /// `updateDeviceGroup(updateDeviceGroupInput: { deviceGroupId, friendlyName })`
    /// - input structure verified via introspection, see the
    /// alexa_graphql_schema memory.
    func renameDeviceGroup(groupId: String, newName: String) async throws -> Bool {
        let query = """
        mutation { updateDeviceGroup(updateDeviceGroupInput: {deviceGroupId: \(Self.jsString(groupId)), friendlyName: \(Self.jsString(newName))}) { deviceGroup { id } } }
        """
        return try await runMutation(query, successKey: "updateDeviceGroup")
    }

    /// `deleteDeviceGroup(deleteDeviceGroupInput: { deviceGroupId })`
    func deleteDeviceGroup(groupId: String) async throws -> Bool {
        let query = """
        mutation { deleteDeviceGroup(deleteDeviceGroupInput: {deviceGroupId: \(Self.jsString(groupId))}) { deviceGroupId } }
        """
        return try await runMutation(query, successKey: "deleteDeviceGroup")
    }

    /// `createDeviceGroup(createDeviceGroupInput: { friendlyName, memberDeviceIds })` -
    /// returns the newly created group (including its `id`).
    func createDeviceGroup(name: String, memberEndpointIds: [String] = []) async throws -> DeviceGroup {
        let idsLiteral = "[" + memberEndpointIds.map(Self.jsString).joined(separator: ", ") + "]"
        let query = """
        mutation { createDeviceGroup(createDeviceGroupInput: {friendlyName: \(Self.jsString(name)), memberDeviceIds: \(idsLiteral)}) { deviceGroup { \
        id friendlyName { value { text } } memberDevices { items { id } } \
        } } }
        """
        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )
        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)
        guard let json = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] else {
            throw AlexaSessionError.invalidResponse
        }
        if let dataDict = json["data"] as? [String: Any],
           let response = dataDict["createDeviceGroup"] as? [String: Any],
           let group = response["deviceGroup"] as? [String: Any] {
            return Self.parseDeviceGroup(from: group)
        }
        let errors = (json["errors"] as? [[String: Any]])?.compactMap { $0["message"] as? String }
        throw AlexaSessionError.graphQLErrors(errors ?? ["Unknown GraphQL error"])
    }

    /// `updateDeviceGroup(updateDeviceGroupInput: { deviceGroupId, memberDeviceIds,
    /// memberDeviceIdsUpdateOperation })` - `operation`'s enumValues (ADD/REMOVE/
    /// REPLACE) confirmed via introspection, see the alexa_graphql_schema memory.
    func updateDeviceGroupMembers(groupId: String, endpointIds: [String], operation: DeviceGroupMemberOperation) async throws -> Bool {
        let idsLiteral = "[" + endpointIds.map(Self.jsString).joined(separator: ", ") + "]"
        let query = """
        mutation { updateDeviceGroup(updateDeviceGroupInput: {deviceGroupId: \(Self.jsString(groupId)), memberDeviceIds: \(idsLiteral), memberDeviceIdsUpdateOperation: \(operation.rawValue)}) { deviceGroup { id } } }
        """
        return try await runMutation(query, successKey: "updateDeviceGroup")
    }

    private func runMutation(_ query: String, successKey: String) async throws -> Bool {
        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )
        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)
        guard let json = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] else {
            throw AlexaSessionError.invalidResponse
        }
        if let dataDict = json["data"] as? [String: Any], dataDict[successKey] != nil {
            return true
        }
        let errors = (json["errors"] as? [[String: Any]])?.compactMap { $0["message"] as? String }
        throw AlexaSessionError.graphQLErrors(errors ?? ["Unknown GraphQL error"])
    }

    private static func parseDevice(from item: [String: Any]) -> Device {
        let friendlyName = item["friendlyName"] as? String ?? ""
        let applianceId = (item["legacyAppliance"] as? [String: Any])?["applianceId"] as? String ?? ""
        let endpointId = item["id"] as? String

        // manufacturer: NameValueObject { value: ValueObject { text: String } }
        let manufacturerName = ((item["manufacturer"] as? [String: Any])?["value"] as? [String: Any])?["text"] as? String

        // displayCategories: DisplayCategories { primary: DisplayCategory { value: String } }
        let displayCategory = ((item["displayCategories"] as? [String: Any])?["primary"] as? [String: Any])?["value"] as? String

        // associatedUnits: Unit { id: String } - despite the plural name, a single object.
        let associatedUnitId = (item["associatedUnits"] as? [String: Any])?["id"] as? String

        // features: [Feature { name, properties: [FeatureProperty] }] - the
        // feature with name == "connectivity" has a Reachability object as
        // its properties entry, with reachabilityStatusValue:
        // OK|UNREACHABLE (confirmed via live testing, see the
        // alexa_graphql_schema memory - there is NO top-level `connectivity`
        // field on Endpoint).
        let connectivityFeature = (item["features"] as? [[String: Any]])?.first { ($0["name"] as? String) == "connectivity" }
        let reachability = (connectivityFeature?["properties"] as? [[String: Any]])?.first { ($0["__typename"] as? String) == "Reachability" }
        let connectivity: Device.Connectivity
        switch reachability?["reachabilityStatusValue"] as? String {
        case "OK": connectivity = .ok
        case "UNREACHABLE": connectivity = .unreachable
        default: connectivity = .unknown
        }

        var rawFields: [String: String] = [:]
        for (key, value) in item where !knownFieldNames.contains(key) {
            rawFields[key] = stringify(value)
        }

        return Device(
            applianceId: applianceId,
            friendlyName: friendlyName,
            decoded: ApplianceIDParser.decode(applianceId),
            connectivity: connectivity,
            manufacturerName: manufacturerName?.isEmpty == false ? manufacturerName : nil,
            displayCategory: displayCategory?.isEmpty == false ? displayCategory : nil,
            endpointId: endpointId,
            associatedUnitId: associatedUnitId,
            rawFields: rawFields
        )
    }

    private static func stringify(_ value: Any) -> String {
        switch value {
        case is NSNull:
            return "–"
        case let string as String:
            return string
        case let number as NSNumber:
            if CFGetTypeID(number) == CFBooleanGetTypeID() {
                return number.boolValue ? "true" : "false"
            }
            return number.stringValue
        case let array as [Any]:
            return array.map(stringify).joined(separator: ", ")
        case let dict as [String: Any]:
            return dict.map { "\($0.key)=\(stringify($0.value))" }.joined(separator: ", ")
        default:
            return String(describing: value)
        }
    }

    // MARK: - Schema introspection

    /// Scalar (or enum) fields can be added directly to the query without a
    /// sub-selection. Object/list-of-object fields (which would need a
    /// sub-selection) are skipped.
    private static func isLeafField(_ field: IntrospectionResponse.DataField.TypeInfo.Field) -> Bool {
        let type = field.type
        if type.kind == "SCALAR" || type.kind == "ENUM" { return true }
        if type.kind == "NON_NULL" || type.kind == "LIST", let inner = type.ofType?.kind {
            return inner == "SCALAR" || inner == "ENUM"
        }
        return false
    }

    /// Formatted "name: Type" list of all endpoint fields for display in the
    /// debug dialog ("Check Fields") - additionally runs breadth-first
    /// through all referenced object/interface types (e.g. `manufacturer`
    /// -> `NameValueObject` -> `value` -> `ValueObject`), so you don't have
    /// to query repeatedly to assemble a valid query.
    func fetchAllEndpointFieldNames() async throws -> String {
        var lines: [String] = []

        // Root query/mutation fields first - shows whether there are
        // dedicated top-level fields like "groups"/"rooms"/"units" (e.g.
        // for room management), instead of only going through "endpoints".
        if let rootFields = try? await fetchRootTypeFields() {
            lines.append(rootFields)
            lines.append("")
        }

        let (typeName, fields) = try await introspectFields()
        lines.append("Type: \(typeName)")
        lines.append("")
        lines += Self.formattedFieldLines(fields)

        var visited: Set<String> = [typeName]
        var queue = Self.nestedTypeNames(in: fields).filter { !visited.contains($0) }
        // Safety net against cyclic (e.g. Endpoint.parentComponent) or very
        // deep type graphs.
        while let nestedTypeName = queue.first, visited.count < 40 {
            queue.removeFirst()
            guard !visited.contains(nestedTypeName) else { continue }
            visited.insert(nestedTypeName)

            guard let details = try? await introspectTypeDetails(named: nestedTypeName) else { continue }
            lines.append("")
            lines.append("--- \(nestedTypeName) (kind: \(details.kind ?? "?")) ---")

            if let nestedFields = details.fields {
                lines += Self.formattedFieldLines(nestedFields)
                queue += Self.nestedTypeNames(in: nestedFields).filter { !visited.contains($0) }
            }
            if let possibleTypes = details.possibleTypes, !possibleTypes.isEmpty {
                lines.append("possibleTypes: " + possibleTypes.compactMap(\.name).joined(separator: ", "))
                queue += possibleTypes.compactMap(\.name).filter { !visited.contains($0) }
            }
            if let enumValues = details.enumValues, !enumValues.isEmpty {
                lines.append("enumValues: " + enumValues.compactMap(\.name).joined(separator: ", "))
            }
        }

        return lines.joined(separator: "\n")
    }

    private static func formattedFieldLines(_ fields: [IntrospectionResponse.DataField.TypeInfo.Field]) -> [String] {
        fields.map { field -> String in
            let fieldTypeName = field.type.name ?? field.type.ofType?.name ?? field.type.kind ?? "?"
            guard let args = field.args, !args.isEmpty else {
                return "\(field.name): \(fieldTypeName)"
            }
            let argsString = args.map { arg -> String in
                let argTypeName = arg.type.name ?? arg.type.ofType?.name ?? arg.type.kind ?? "?"
                return "\(arg.name): \(argTypeName)"
            }.joined(separator: ", ")
            return "\(field.name)(\(argsString)): \(fieldTypeName)"
        }.sorted()
    }

    private static func nestedTypeNames(in fields: [IntrospectionResponse.DataField.TypeInfo.Field]) -> [String] {
        Set(fields.compactMap { field -> String? in
            let kind = (field.type.kind == "NON_NULL" || field.type.kind == "LIST") ? field.type.ofType?.kind : field.type.kind
            guard kind == "OBJECT" || kind == "INTERFACE" || kind == "UNION" || kind == "INPUT_OBJECT" else { return nil }
            return field.type.name ?? field.type.ofType?.name
        }).sorted()
    }

    /// Lists the top-level fields of the root Query and Mutation types (e.g.
    /// "endpoints", but maybe also "groups"/"rooms"/"units" or mutations
    /// like "renameGroup") - relevant for the rooms/groups research, since
    /// so far we've only gone through the "endpoints" root query field.
    private func fetchRootTypeFields() async throws -> String {
        let query = "query { __schema { queryType { name } mutationType { name } } }"
        let script = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(query))}"
        )
        let raw = try await evaluate(script)
        let bodyData = try decodeEnvelopeBody(raw)
        let response = try JSONDecoder().decode(SchemaRootTypesResponse.self, from: bodyData)
        guard let schema = response.data?.schema else {
            throw AlexaSessionError.graphQLErrors(response.errors?.map(\.message) ?? ["__schema not accessible."])
        }

        var lines: [String] = []
        if let queryTypeName = schema.queryType?.name {
            let fields = (try? await introspectType(named: queryTypeName)) ?? []
            lines.append("=== Root Query (\(queryTypeName)) ===")
            lines += Self.formattedFieldLines(fields)
        }
        lines.append("")
        if let mutationTypeName = schema.mutationType?.name {
            let fields = (try? await introspectType(named: mutationTypeName)) ?? []
            lines.append("=== Root Mutation (\(mutationTypeName)) ===")
            lines += Self.formattedFieldLines(fields)
        } else {
            lines.append("(no mutation root type found)")
        }

        // Look specifically into the return types relevant to rooms/device
        // groups (not a full, huge schema BFS - Home/Automations/etc. would
        // otherwise blow up the output).
        var visited: Set<String> = []
        var queue = [
            "ListDeviceGroupsResponse", "DeviceGroup",
            "CreateDeviceGroupResponse", "UpdateDeviceGroupsResponse",
            "DeleteDeviceGroupResponse", "UpdateDeviceGroupSpeakerConfigurationResponse",
            "Home", "HomesResponse", "SetEndpointFriendlyNameResponse",
            // INPUT_OBJECT types of the relevant mutation/query arguments -
            // their fields come back under `inputFields`, not `fields`.
            "ListDeviceGroupsInput", "CreateDeviceGroupInput",
            "UpdateDeviceGroupInput", "DeleteDeviceGroupInput",
            "PaginationParams", "CollectionOperationOptions", "PaginatedEndpoints"
        ]
        while let typeName = queue.first, visited.count < 30 {
            queue.removeFirst()
            guard !visited.contains(typeName) else { continue }
            visited.insert(typeName)

            guard let details = try? await introspectTypeDetails(named: typeName) else { continue }
            lines.append("")
            lines.append("--- \(typeName) (kind: \(details.kind ?? "?")) ---")
            if let fields = details.fields {
                lines += Self.formattedFieldLines(fields)
                queue += Self.nestedTypeNames(in: fields).filter { !visited.contains($0) }
            }
            if let inputFields = details.inputFields {
                lines += Self.formattedFieldLines(inputFields)
                queue += Self.nestedTypeNames(in: inputFields).filter { !visited.contains($0) }
            }
            if let possibleTypes = details.possibleTypes, !possibleTypes.isEmpty {
                lines.append("possibleTypes: " + possibleTypes.compactMap(\.name).joined(separator: ", "))
            }
            if let enumValues = details.enumValues, !enumValues.isEmpty {
                lines.append("enumValues: " + enumValues.compactMap(\.name).joined(separator: ", "))
            }
        }

        return lines.joined(separator: "\n")
    }

    private func introspectFields() async throws -> (typeName: String, fields: [IntrospectionResponse.DataField.TypeInfo.Field]) {
        let typenameQuery = "query { endpoints { items { __typename } } }"
        let typenameScript = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(typenameQuery))}"
        )
        let typenameRaw = try await evaluate(typenameScript)
        let typenameData = try decodeEnvelopeBody(typenameRaw)
        let typenameResponse = try JSONDecoder().decode(TypenameResponse.self, from: typenameData)
        guard let typeName = typenameResponse.data?.endpoints.items.first?.typename else {
            throw AlexaSessionError.graphQLErrors(typenameResponse.errors?.map(\.message) ?? ["No __typename received - maybe there are no devices."])
        }
        let details = try await introspectTypeDetails(named: typeName)
        return (typeName, details.fields ?? [])
    }

    private func introspectType(named typeName: String) async throws -> [IntrospectionResponse.DataField.TypeInfo.Field] {
        let details = try await introspectTypeDetails(named: typeName)
        guard let fields = details.fields else {
            throw AlexaSessionError.graphQLErrors(["Type '\(typeName)' (kind: \(details.kind ?? "?")) has no 'fields' - likely UNION/ENUM/SCALAR, see possibleTypes/enumValues."])
        }
        return fields
    }

    /// Returns kind/fields/possibleTypes/enumValues of a type - unlike
    /// `introspectType`, this is also usable when `fields` is `null` (e.g.
    /// for UNION types like the presumed `Enablement`).
    private func introspectTypeDetails(named typeName: String) async throws -> IntrospectionResponse.DataField.TypeInfo {
        let introspectionQuery = """
        query { __type(name: \(Self.jsString(typeName))) { \
        name kind \
        fields { name args { name type { name kind ofType { name kind } } } type { name kind ofType { name kind } } } \
        inputFields { name type { name kind ofType { name kind } } } \
        possibleTypes { name } \
        enumValues(includeDeprecated: true) { name } \
        } }
        """
        let introspectionScript = Self.fetchScript(
            path: "/nexus/v1/graphql",
            method: "POST",
            jsonBody: "{query: \(Self.jsString(introspectionQuery))}"
        )
        let introspectionRaw = try await evaluate(introspectionScript)
        let introspectionData = try decodeEnvelopeBody(introspectionRaw)
        let introspectionResponse = try JSONDecoder().decode(IntrospectionResponse.self, from: introspectionData)
        guard let details = introspectionResponse.data?.typeInfo else {
            throw AlexaSessionError.graphQLErrors(introspectionResponse.errors?.map(\.message) ?? ["Introspection is disabled on this server."])
        }
        return details
    }

    private func decodeEnvelopeBody(_ raw: String) throws -> Data {
        guard let envelopeData = raw.data(using: .utf8),
              let envelope = try? JSONDecoder().decode(StatusEnvelope.self, from: envelopeData) else {
            throw AlexaSessionError.invalidResponse
        }
        guard envelope.status == 200 else {
            throw AlexaSessionError.httpError(envelope.status)
        }
        guard let bodyString = envelope.body, let bodyData = bodyString.data(using: .utf8) else {
            throw AlexaSessionError.invalidResponse
        }
        return bodyData
    }

    // MARK: - Deleting a device

    func deleteDevice(applianceId: String) async throws -> Bool {
        guard let encoded = Self.encodeURIComponent(applianceId) else {
            throw AlexaSessionError.invalidResponse
        }

        var extraHeaders = ""
        if !csrfToken.isEmpty {
            extraHeaders = ", \"csrf\": \(Self.jsString(csrfToken))"
        }

        let script = """
        try {
          const res = await fetch('/api/phoenix/appliance/\(encoded)', {
            method: 'DELETE',
            credentials: 'include',
            headers: { "Accept": "application/json", "Content-Type": "application/json"\(extraHeaders) }
          });
          return JSON.stringify({status: res.status});
        } catch (e) {
          return JSON.stringify({status: -1, body: String(e)});
        }
        """

        let raw = try await evaluate(script)
        guard let data = raw.data(using: .utf8),
              let envelope = try? JSONDecoder().decode(StatusEnvelope.self, from: data) else {
            throw AlexaSessionError.invalidResponse
        }
        return envelope.status == 200
    }

    // MARK: - Helpers

    private static func fetchScript(path: String, method: String, jsonBody: String) -> String {
        """
        try {
          const res = await fetch('\(path)', {
            method: '\(method)',
            credentials: 'include',
            headers: {"Content-Type": "application/json", "Accept": "application/json"},
            body: JSON.stringify(\(jsonBody))
          });
          const text = await res.text();
          return JSON.stringify({status: res.status, body: text});
        } catch (e) {
          return JSON.stringify({status: -1, body: String(e)});
        }
        """
    }

    private static func jsString(_ value: String) -> String {
        guard let data = try? JSONEncoder().encode(value), let s = String(data: data, encoding: .utf8) else {
            return "\"\""
        }
        return s
    }

    /// Replacement for JS `encodeURIComponent` (RFC3986 unreserved characters).
    private static func encodeURIComponent(_ value: String) -> String? {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-_.!~*'()")
        return value.addingPercentEncoding(withAllowedCharacters: allowed)
    }
}

// MARK: - GraphQL response model

private struct SchemaRootTypesResponse: Decodable {
    struct DataField: Decodable {
        struct Schema: Decodable {
            struct NamedType: Decodable { let name: String? }
            let queryType: NamedType?
            let mutationType: NamedType?
        }
        let schema: Schema?
        enum CodingKeys: String, CodingKey { case schema = "__schema" }
    }
    let data: DataField?
    let errors: [GraphQLError]?
}

private struct TypenameResponse: Decodable {
    struct DataField: Decodable {
        struct Endpoints: Decodable {
            struct Item: Decodable {
                let typename: String
                enum CodingKeys: String, CodingKey { case typename = "__typename" }
            }
            let items: [Item]
        }
        let endpoints: Endpoints
    }
    let data: DataField?
    let errors: [GraphQLError]?
}

private struct IntrospectionResponse: Decodable {
    struct DataField: Decodable {
        struct TypeInfo: Decodable {
            struct Field: Decodable {
                struct FieldType: Decodable {
                    struct OfType: Decodable {
                        let name: String?
                        let kind: String?
                    }
                    let name: String?
                    let kind: String?
                    let ofType: OfType?
                }
                struct Argument: Decodable {
                    let name: String
                    let type: FieldType
                }
                let name: String
                let type: FieldType
                let args: [Argument]?
            }
            struct NamedType: Decodable { let name: String? }
            let kind: String?
            let fields: [Field]?
            /// For INPUT_OBJECT types (e.g. `CreateDeviceGroupInput`),
            /// GraphQL introspection returns the fields under
            /// `inputFields`, not under `fields` (which is `null` for
            /// INPUT_OBJECT per spec).
            let inputFields: [Field]?
            let possibleTypes: [NamedType]?
            let enumValues: [NamedType]?
        }
        let typeInfo: TypeInfo?
        enum CodingKeys: String, CodingKey { case typeInfo = "__type" }
    }
    let data: DataField?
    let errors: [GraphQLError]?
}

private struct GraphQLError: Decodable {
    let message: String
}

// MARK: - WKNavigationDelegate

extension AlexaWebSession: WKNavigationDelegate {
    nonisolated func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Task { @MainActor in
            self.isLoading = false
            self.currentURL = webView.url?.absoluteString
            if self.shouldCheckLoginOnNextLoad {
                await self.checkLoginStatus()
            }
            self.resumePendingNavigation()
        }
    }

    nonisolated func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        Task { @MainActor in
            self.isLoading = false
            self.lastError = error.localizedDescription
            self.resumePendingNavigation()
        }
    }

    nonisolated func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        Task { @MainActor in
            self.isLoading = false
            self.lastError = error.localizedDescription
            self.resumePendingNavigation()
        }
    }
}
