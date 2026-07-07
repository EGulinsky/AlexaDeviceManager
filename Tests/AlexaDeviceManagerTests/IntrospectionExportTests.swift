import XCTest
@testable import AlexaDeviceManager

/// Not a classic unit test - calls live GraphQL introspection using the
/// Amazon session cookies already persisted in the app container, and
/// prints the result to the test logs. This lets schema research be
/// automated via `xcodebuild test` without operating the app GUI.
/// Prerequisite: having signed in once in the running app via "Sign In"
/// (see AlexaWebSession.attemptAutoLogin).
final class IntrospectionExportTests: XCTestCase {
    @MainActor
    func testExportEndpointAndRootSchemaFields() async throws {
        let session = AlexaWebSession()
        let loggedIn = await session.attemptAutoLogin()
        guard loggedIn else {
            XCTFail("Not signed in - please sign in once in the app via 'Sign In' so the session cookies are persisted in the app container.")
            return
        }

        let output = try await session.fetchAllEndpointFieldNames()
        print("===SCHEMA-DUMP-START===")
        print(output)
        print("===SCHEMA-DUMP-END===")
    }

    @MainActor
    func testFetchDeviceGroups() async throws {
        let session = AlexaWebSession()
        let loggedIn = await session.attemptAutoLogin()
        guard loggedIn else {
            XCTFail("Not signed in - please sign in once in the app via 'Sign In'.")
            return
        }

        let groups = try await session.fetchDeviceGroups()
        print("===DEVICEGROUPS-DUMP-START===")
        for group in groups {
            print("\(group.name) (id: \(group.id)): \(group.memberEndpointIds.count) devices")
            for endpointId in group.memberEndpointIds {
                print("  - \(endpointId)")
            }
        }
        print("Total \(groups.count) groups.")
        print("===DEVICEGROUPS-DUMP-END===")
    }

    /// Checks create/rename/add-member/remove-member/delete in a single,
    /// self-cleaning run against the real API - creates a clearly
    /// identifiable test group and deletes it again afterwards, regardless
    /// of whether the intermediate steps succeeded.
    @MainActor
    func testDeviceGroupMutationsRoundTrip() async throws {
        let session = AlexaWebSession()
        let loggedIn = await session.attemptAutoLogin()
        guard loggedIn else {
            XCTFail("Not signed in.")
            return
        }

        let devices = try await session.fetchDevices()
        guard let testDevice = devices.first(where: { $0.endpointId != nil }) else {
            XCTFail("No device with an endpointId found to run the member test.")
            return
        }
        let endpointId = testDevice.endpointId!

        let testName = "ClaudeTest-\(Int(Date().timeIntervalSince1970))"
        print("===MUTATION-ROUNDTRIP-START===")
        print("Test device: \(testDevice.friendlyName) (endpointId: \(endpointId))")

        let created = try await session.createDeviceGroup(name: testName, memberEndpointIds: [])
        print("Created: \(created.name) (id: \(created.id)), members: \(created.memberEndpointIds.count)")

        // Cleanup (deleting the test group) must always be awaited before
        // the test function returns - so no `defer` with a Task, instead
        // intermediate steps in do/catch and synchronous cleanup afterwards.
        var caughtError: Error?
        do {
            let renamed = try await session.renameDeviceGroup(groupId: created.id, newName: "\(testName)-renamed")
            print("Renamed: \(renamed)")

            let added = try await session.updateDeviceGroupMembers(groupId: created.id, endpointIds: [endpointId], operation: .add)
            print("Member added: \(added)")

            let groupsAfterAdd = try await session.fetchDeviceGroups()
            let memberCountAfterAdd = groupsAfterAdd.first(where: { $0.id == created.id })?.memberEndpointIds.count ?? -1
            print("Member count after ADD: \(memberCountAfterAdd)")

            let removed = try await session.updateDeviceGroupMembers(groupId: created.id, endpointIds: [endpointId], operation: .remove)
            print("Member removed: \(removed)")

            let groupsAfterRemove = try await session.fetchDeviceGroups()
            let memberCountAfterRemove = groupsAfterRemove.first(where: { $0.id == created.id })?.memberEndpointIds.count ?? -1
            print("Member count after REMOVE: \(memberCountAfterRemove)")
        } catch {
            print("Error during intermediate steps: \(error)")
            caughtError = error
        }

        let deleted = (try? await session.deleteDeviceGroup(groupId: created.id)) ?? false
        print("Cleanup: test group deleted = \(deleted)")
        print("===MUTATION-ROUNDTRIP-END===")

        if let caughtError {
            throw caughtError
        }
    }

    /// Tests whether the online/offline status can be queried via
    /// `features { properties { ... on Reachability { reachabilityStatusValue } } }`,
    /// since `connectivity` doesn't exist on this endpoint type (see the
    /// alexa_graphql_schema memory).
    @MainActor
    func testReachabilityViaFeatures() async throws {
        let session = AlexaWebSession()
        let loggedIn = await session.attemptAutoLogin()
        guard loggedIn else {
            XCTFail("Not signed in.")
            return
        }

        let query = """
        query { endpoints { items { \
        friendlyName \
        legacyAppliance { applianceId } \
        features { name instance properties { __typename ... on Reachability { reachabilityStatusValue } } } \
        } } }
        """
        let raw = try await session.debugRawQuery(query)
        print("===REACHABILITY-DUMP-START===")
        print(raw)
        print("===REACHABILITY-DUMP-END===")
    }
}
