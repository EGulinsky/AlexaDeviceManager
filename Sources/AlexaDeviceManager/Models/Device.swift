import Foundation

struct Device: Identifiable, Hashable {
    enum Connectivity: String {
        case ok
        case unreachable
        case unknown
    }

    /// Sentinel skill ID for devices without a recognizable `SKILL_...` format
    /// in the applianceId (native Amazon devices, Sonos, Ring etc., see
    /// NOTES.md #2). Stored as a plain struct constant (not on the
    /// @MainActor view model) so it's also usable from nonisolated contexts
    /// (e.g. the sort comparator).
    static let unknownSkillId = "unknown"

    let applianceId: String
    let friendlyName: String
    let decoded: DecodedApplianceID?
    var connectivity: Connectivity = .unknown
    /// Manufacturer/brand name supplied by Amazon (for skill-linked devices
    /// this is often identical to the skill's own name, e.g. "Home
    /// Assistant", "Philips Hue"). Best-effort field, see
    /// `AlexaWebSession.fetchDevices`.
    var manufacturerName: String?
    /// Amazon's own standardized device category
    /// (`displayCategories.primary.value`, e.g. "LIGHT", "SMARTPLUG",
    /// "THERMOSTAT") - much more reliable than parsing the applianceId,
    /// since it's assigned by Amazon itself for every endpoint type, not
    /// just for Home Assistant skills.
    var displayCategory: String?
    /// Internal endpoint `id` field (not the same as the applianceId from
    /// `legacyAppliance`). Needed to link zone/room pseudo-endpoints to
    /// regular devices via `associatedUnitIds` (see the
    /// alexa_graphql_schema memory, Phase 1 of the rooms research).
    var endpointId: String?
    /// ID of the `Unit` (room/zone) this device is assigned to according to
    /// `associatedUnits { id }` (despite the plural name, introspection
    /// shows this is a single `Unit` object, not a list) - best-effort, see
    /// `AlexaWebSession.fetchDevices`.
    var associatedUnitId: String?
    /// All other scalar fields the GraphQL introspection found on the
    /// endpoint type that the app doesn't know about explicitly - shown as
    /// raw text in a dynamic table column, see `DeviceListView`.
    var rawFields: [String: String] = [:]

    var id: String { applianceId }

    var skillId: String? { decoded?.skillId }

    /// Grouping key for "By integration": the real skill ID if available,
    /// otherwise specifically "Amazon" for native Echo/Amazon devices (which
    /// don't have a `SKILL_...` applianceId format but do report
    /// `manufacturer: Amazon`) - that was the one case explicitly called
    /// out as a problem. Other manufacturers (e.g. locally detected smart
    /// TVs) are deliberately NOT split out individually, or the list
    /// fragments into many one-device buckets - those stay grouped under
    /// `unknownSkillId`.
    var integrationGroupKey: String {
        if let skillId { return skillId }
        if manufacturerName == "Amazon" { return "Amazon" }
        return Device.unknownSkillId
    }

    var typeLabel: String {
        if let displayCategory, !displayCategory.isEmpty {
            return AlexaDisplayCategory.label(for: displayCategory)
        }
        guard let kind = homeAssistantDomainKind else { return "Unknown" }
        return HomeAssistantDomain.label(for: kind)
    }

    /// SF Symbol name matching the device type - purely client-side (see
    /// AlexaDisplayCategory/HomeAssistantDomain), no icon field was found in
    /// the API.
    var typeSymbolName: String {
        if let displayCategory, !displayCategory.isEmpty {
            return AlexaDisplayCategory.symbolName(for: displayCategory)
        }
        guard let kind = homeAssistantDomainKind else { return "questionmark.circle" }
        return HomeAssistantDomain.symbolName(for: kind)
    }

    /// Not every applianceId suffix is "<HA-domain>#<object_id>" (see
    /// NOTES.md #2) - Alexa's own routines/areas come as e.g. "Scene:<uuid>"
    /// or "Zone:<uuid>" without a "#". In that case the actual kind sits
    /// before the ":", the rest is just a UUID.
    private var homeAssistantDomainKind: String? {
        guard let domain = decoded?.domain, !domain.isEmpty else { return nil }
        return domain.split(separator: ":", maxSplits: 1).first.map(String.init) ?? domain
    }
}
