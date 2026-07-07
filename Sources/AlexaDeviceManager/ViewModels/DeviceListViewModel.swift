import Foundation

@MainActor
final class DeviceListViewModel: ObservableObject {
    @Published var devices: [Device] = []
    @Published var deviceGroups: [DeviceGroup] = []
    @Published var isBusy = false
    @Published var statusMessage: String?
    @Published var progress: (done: Int, total: Int)?

    let session: AlexaWebSession
    let integrationStore: IntegrationStore

    init(session: AlexaWebSession, integrationStore: IntegrationStore) {
        self.session = session
        self.integrationStore = integrationStore
    }

    func refresh() async {
        isBusy = true
        defer { isBusy = false }
        do {
            devices = try await session.fetchDevices()
            // Groups are a separate GraphQL query (listDeviceGroups) - if
            // that fails for some reason, it shouldn't block the actual
            // device list (hence the separate try?).
            deviceGroups = (try? await session.fetchDeviceGroups()) ?? []
            statusMessage = "\(devices.count) devices loaded."
        } catch {
            statusMessage = "Error loading: \(error.localizedDescription)"
        }
    }

    // MARK: - Grouping

    var groupedBySkill: [(skillId: String, devices: [Device])] {
        Dictionary(grouping: devices) { $0.integrationGroupKey }
            .map { (skillId: $0.key, devices: $0.value) }
            .sorted { integrationLabel(for: $0.skillId) < integrationLabel(for: $1.skillId) }
    }

    var groupedByType: [(type: String, devices: [Device])] {
        Dictionary(grouping: devices) { $0.typeLabel }
            .map { (type: $0.key, devices: $0.value) }
            .sorted { $0.type < $1.type }
    }

    /// All Alexa "Groups" (`listDeviceGroups`) - including empty ones, since
    /// it's normal in Alexa itself for a group to (still) have no devices.
    var groupedByDeviceGroup: [(group: DeviceGroup, devices: [Device])] {
        deviceGroups.map { group in
            let members = devices.filter { device in
                guard let endpointId = device.endpointId else { return false }
                return group.memberEndpointIds.contains(endpointId)
            }
            return (group: group, devices: members)
        }.sorted { $0.group.name < $1.group.name }
    }

    func devicesInGroup(_ groupId: String) -> [Device] {
        guard let group = deviceGroups.first(where: { $0.id == groupId }) else { return [] }
        return devices.filter { device in
            guard let endpointId = device.endpointId else { return false }
            return group.memberEndpointIds.contains(endpointId)
        }
    }

    /// A manually set name always takes precedence. `key` is either a real
    /// skill ID, a manufacturer name (see `Device.integrationGroupKey` -
    /// e.g. "Amazon" for Echo devices without a SKILL_ format), or the
    /// `unknownSkillId` sentinel. For real skill IDs we use - if Amazon
    /// supplies it - the `manufacturer` value of that group's devices as
    /// the readable name (e.g. "Home Assistant" instead of the shortened
    /// skill ID).
    func integrationLabel(for key: String) -> String {
        if key == Device.unknownSkillId {
            return "Unknown (no skill detected)"
        }
        if let name = integrationStore.meta(for: key).displayName {
            return name
        }
        guard key.hasPrefix("amzn1.ask.skill.") else {
            // Already a readable manufacturer name (e.g. "Amazon").
            return key
        }
        if let manufacturer = devices.first(where: { $0.skillId == key })?.manufacturerName {
            return manufacturer
        }
        return integrationStore.label(for: key)
    }

    // MARK: - Batch filters

    func unresponsiveDevices() -> [Device] {
        devices.filter { $0.connectivity == .unreachable }
    }

    /// Amazon provides an `enablement` field on the endpoint type for this,
    /// whose exact structure (presumably a UNION type) hasn't been resolved
    /// yet - until that's clarified, there's no automatic detection here.
    func devicesFromDisabledIntegrations() -> [Device] {
        []
    }

    // MARK: - Managing groups

    func createGroup(name: String, withMembers memberDevices: [Device] = []) async {
        guard !name.isEmpty else { return }
        let endpointIds = memberDevices.compactMap { $0.endpointId }
        do {
            _ = try await session.createDeviceGroup(name: name, memberEndpointIds: endpointIds)
            statusMessage = endpointIds.isEmpty
                ? "Group “\(name)” created."
                : "Group “\(name)” created with \(endpointIds.count) device(s)."
        } catch {
            statusMessage = "Error creating group: \(error.localizedDescription)"
        }
        await refreshGroupsOnly()
    }

    func renameGroup(_ group: DeviceGroup, to newName: String) async {
        guard !newName.isEmpty, newName != group.name else { return }
        do {
            _ = try await session.renameDeviceGroup(groupId: group.id, newName: newName)
            statusMessage = "Group renamed to “\(newName)”."
        } catch {
            statusMessage = "Error renaming: \(error.localizedDescription)"
        }
        await refreshGroupsOnly()
    }

    func deleteGroup(_ group: DeviceGroup) async {
        do {
            _ = try await session.deleteDeviceGroup(groupId: group.id)
            statusMessage = "Group “\(group.name)” deleted."
        } catch {
            statusMessage = "Error deleting: \(error.localizedDescription)"
        }
        await refreshGroupsOnly()
    }

    func addDevice(_ device: Device, toGroup group: DeviceGroup) async {
        await addDevices([device], toGroup: group)
    }

    func removeDevice(_ device: Device, fromGroup group: DeviceGroup) async {
        await removeDevices([device], fromGroup: group)
    }

    /// Bulk variant for a multi-selection in the table. Calls
    /// `updateDeviceGroupMembers` once PER device, not with all endpoint IDs
    /// in a single call: Amazon's backend accepts a `memberDeviceIds` array
    /// with multiple entries and responds with success, but demonstrably
    /// only processes the FIRST id when tested live - the rest are silently
    /// ignored (confirmed via debug logging, 2026-07-06: out of 3 sent IDs,
    /// only the first one actually took effect). Individual calls are the
    /// only reliable way.
    func addDevices(_ devicesToAdd: [Device], toGroup group: DeviceGroup) async {
        let endpointIds = devicesToAdd.compactMap { $0.endpointId }
        guard !endpointIds.isEmpty else { return }
        var succeeded = 0
        for endpointId in endpointIds {
            do {
                _ = try await session.updateDeviceGroupMembers(groupId: group.id, endpointIds: [endpointId], operation: .add)
                succeeded += 1
            } catch {
                // Single device failed - keep going with the rest.
            }
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
        statusMessage = "\(succeeded)/\(endpointIds.count) device(s) added to “\(group.name)”."
        await refreshGroupsOnly()
    }

    func removeDevices(_ devicesToRemove: [Device], fromGroup group: DeviceGroup) async {
        let endpointIds = devicesToRemove.compactMap { $0.endpointId }
        guard !endpointIds.isEmpty else { return }
        var succeeded = 0
        for endpointId in endpointIds {
            do {
                _ = try await session.updateDeviceGroupMembers(groupId: group.id, endpointIds: [endpointId], operation: .remove)
                succeeded += 1
            } catch {
                // Single device failed - keep going with the rest.
            }
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
        statusMessage = "\(succeeded)/\(endpointIds.count) device(s) removed from “\(group.name)”."
        await refreshGroupsOnly()
    }

    /// Moves a multi-selection from one group to another (e.g. via drag &
    /// drop or the context menu) - remove + add as two separate mutations,
    /// since the API has no "move" operation.
    func moveDevices(_ devicesToMove: [Device], fromGroup source: DeviceGroup?, toGroup destination: DeviceGroup) async {
        if let source, source.id != destination.id {
            await removeDevices(devicesToMove, fromGroup: source)
        }
        await addDevices(devicesToMove, toGroup: destination)
    }

    /// Only reload groups (not the whole, larger device list) after a group mutation.
    private func refreshGroupsOnly() async {
        deviceGroups = (try? await session.fetchDeviceGroups()) ?? deviceGroups
    }

    // MARK: - Deleting

    func delete(_ devicesToDelete: [Device]) async {
        guard !devicesToDelete.isEmpty else { return }
        isBusy = true
        progress = (0, devicesToDelete.count)

        var succeeded = 0
        var failed = 0
        for (index, device) in devicesToDelete.enumerated() {
            do {
                let ok = try await session.deleteDevice(applianceId: device.applianceId)
                if ok { succeeded += 1 } else { failed += 1 }
            } catch {
                failed += 1
            }
            progress = (index + 1, devicesToDelete.count)
            // Small throttle since no official rate limit is documented.
            try? await Task.sleep(nanoseconds: 300_000_000)
        }

        statusMessage = "\(succeeded) deleted, \(failed) failed."
        progress = nil
        isBusy = false
        await refresh()
    }
}
