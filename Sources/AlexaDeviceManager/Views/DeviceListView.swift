import SwiftUI

struct DeviceListView: View {
    let devices: [Device]
    @Binding var selection: Set<String>
    @ObservedObject var viewModel: DeviceListViewModel
    @State private var sortOrder: [DeviceSortComparator] = [DeviceSortComparator(field: .name)]
    /// Last known multi-selection (>1 item). `Table` appears to sometimes
    /// collapse `selection` down to the single row under the cursor as soon
    /// as a drag starts on an already-selected row, before `.draggable`
    /// computes its payload value - which caused dragging a multi-selection
    /// to only move 1 device. This snapshot is retained until a new real
    /// multi-selection occurs, and serves as a fallback for the drag
    /// payload.
    @State private var lastMultiSelection: Set<String> = []

    var body: some View {
        Table(sortedDevices, selection: $selection, sortOrder: $sortOrder) {
            TableColumn("Name", sortUsing: DeviceSortComparator(field: .name)) { device in
                Text(device.friendlyName)
                    .contextMenu {
                        GroupMembershipMenu(device: device, viewModel: viewModel)
                    }
                    // Drag device(s) onto a group in the sidebar, see
                    // IntegrationsSidebar.GroupRow.dropDestination. If the
                    // dragged row is part of a multi-selection, the whole
                    // selection is bundled (DeviceDragPayload), otherwise
                    // just the one device under the cursor.
                    .draggable(dragPayload(for: device)) {
                        dragPreview(for: device)
                    }
            }
            TableColumn("Type", sortUsing: DeviceSortComparator(field: .type)) { device in
                Label(device.typeLabel, systemImage: device.typeSymbolName)
            }
            TableColumn("Integration", sortUsing: DeviceSortComparator(field: .integration)) { device in
                IntegrationCell(groupKey: device.integrationGroupKey, viewModel: viewModel)
            }
            TableColumn("Status", sortUsing: DeviceSortComparator(field: .status)) { device in
                connectivityBadge(device.connectivity)
            }
            TableColumn("applianceId", sortUsing: DeviceSortComparator(field: .applianceId)) { device in
                Text(device.applianceId)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            // SwiftUI's Table doesn't allow a runtime-determined column
            // count (neither ForEach nor for-loops in the
            // TableColumnBuilder) - so all additional fields that GraphQL
            // introspection found (see AlexaWebSession.fetchDevices) end up
            // in this one column with a popover detail view instead of
            // real columns.
            TableColumn("All Fields") { device in
                RawFieldsCell(device: device)
            }
        }
        .overlay {
            if devices.isEmpty {
                ContentUnavailableView(
                    "No Devices",
                    systemImage: "wifi.slash",
                    description: Text("Sign in and tap “Refresh” to load devices.")
                )
            }
        }
        .onChange(of: selection) { _, newValue in
            if newValue.count > 1 {
                lastMultiSelection = newValue
            }
        }
    }

    // "All Fields" is a dictionary with a variable key set per device -
    // there's no meaningful sort criterion for that. All other columns
    // (including "Integration", via `DeviceSortComparator`) are sortable.
    private var sortedDevices: [Device] {
        devices.sorted(using: sortOrder)
    }

    /// If you drag a row that's part of the (possibly already collapsed,
    /// see `lastMultiSelection`) multi-selection, the whole selection is
    /// returned - so multiple selected devices can be dragged onto a group
    /// in a single gesture instead of just the one row under the cursor.
    private func draggedDeviceIDs(for device: Device) -> Set<String> {
        if lastMultiSelection.count > 1, lastMultiSelection.contains(device.id), selection.contains(device.id) {
            return lastMultiSelection
        }
        return [device.id]
    }

    private func dragPayload(for device: Device) -> String {
        let ids = draggedDeviceIDs(for: device)
        let applianceIds = devices.filter { ids.contains($0.id) }.map { $0.applianceId }
        return DeviceDragPayload.encode(applianceIds)
    }

    @ViewBuilder
    private func dragPreview(for device: Device) -> some View {
        let count = draggedDeviceIDs(for: device).count
        if count > 1 {
            Label("\(count) devices", systemImage: "square.stack.3d.up.fill")
                .padding(6)
        } else {
            Label(device.friendlyName, systemImage: device.typeSymbolName)
                .padding(6)
        }
    }

    @ViewBuilder
    private func connectivityBadge(_ connectivity: Device.Connectivity) -> some View {
        switch connectivity {
        case .ok:
            Label("OK", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
        case .unreachable:
            Label("Unreachable", systemImage: "xmark.circle.fill").foregroundStyle(.red)
        case .unknown:
            Label("Unknown", systemImage: "questionmark.circle").foregroundStyle(.secondary)
        }
    }
}

private struct RawFieldsCell: View {
    let device: Device
    @State private var showDetails = false

    var body: some View {
        Button {
            showDetails = true
        } label: {
            Text(device.rawFields.isEmpty ? "–" : "Show \(device.rawFields.count) Fields")
        }
        .buttonStyle(.link)
        .popover(isPresented: $showDetails) {
            allFieldsList
                .padding()
                .frame(minWidth: 320, maxHeight: 400)
        }
    }

    private var allFieldsList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                Text(device.friendlyName)
                    .font(.headline)
                Divider()
                fieldRow("friendlyName", device.friendlyName)
                fieldRow("applianceId", device.applianceId)
                if let manufacturerName = device.manufacturerName {
                    fieldRow("manufacturerName", manufacturerName)
                }
                fieldRow("connectivity", device.connectivity.rawValue)
                ForEach(device.rawFields.keys.sorted(), id: \.self) { key in
                    fieldRow(key, device.rawFields[key] ?? "")
                }
            }
        }
    }

    private func fieldRow(_ key: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(key)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(.body, design: .monospaced))
                .textSelection(.enabled)
        }
    }
}

private struct GroupMembershipMenu: View {
    let device: Device
    @ObservedObject var viewModel: DeviceListViewModel

    var body: some View {
        Menu("Add to Group") {
            if groupsNotContaining.isEmpty {
                Text("No other groups")
            }
            ForEach(groupsNotContaining, id: \.id) { group in
                Button(group.name) {
                    Task { await viewModel.addDevice(device, toGroup: group) }
                }
            }
        }
        Menu("Remove from Group") {
            if groupsContaining.isEmpty {
                Text("Not in any group")
            }
            ForEach(groupsContaining, id: \.id) { group in
                Button(group.name) {
                    Task { await viewModel.removeDevice(device, fromGroup: group) }
                }
            }
        }
    }

    private var groupsContaining: [DeviceGroup] {
        guard let endpointId = device.endpointId else { return [] }
        return viewModel.deviceGroups.filter { $0.memberEndpointIds.contains(endpointId) }
    }

    private var groupsNotContaining: [DeviceGroup] {
        guard let endpointId = device.endpointId else { return viewModel.deviceGroups }
        return viewModel.deviceGroups.filter { !$0.memberEndpointIds.contains(endpointId) }
    }
}

private struct IntegrationCell: View {
    let groupKey: String
    @ObservedObject var viewModel: DeviceListViewModel
    @State private var isEditingName = false
    @State private var nameDraft = ""

    var body: some View {
        Text(viewModel.integrationLabel(for: groupKey))
            .contextMenu {
                Button("Edit Display Name…") {
                    nameDraft = viewModel.integrationStore.meta(for: groupKey).displayName ?? ""
                    isEditingName = true
                }
            }
            .alert("Display Name for Integration", isPresented: $isEditingName) {
                TextField("Name", text: $nameDraft)
                Button("Save") {
                    viewModel.integrationStore.setDisplayName(nameDraft, for: groupKey)
                }
                Button("Cancel", role: .cancel) {}
            }
    }
}
