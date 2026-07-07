import SwiftUI

struct IntegrationsSidebar: View {
    @ObservedObject var viewModel: DeviceListViewModel
    @ObservedObject var integrationStore: IntegrationStore
    @Binding var selectedFilter: DeviceFilter
    @State private var isCreatingGroup = false
    @State private var newGroupName = ""

    var body: some View {
        List(selection: Binding(
            get: { selectedFilter },
            set: { if let value = $0 { selectedFilter = value } }
        )) {
            Section("Overview") {
                Label("All Devices (\(viewModel.devices.count))", systemImage: "square.grid.2x2")
                    .tag(DeviceFilter.all)
                Label("Not Responding (\(viewModel.unresponsiveDevices().count))", systemImage: "exclamationmark.triangle")
                    .tag(DeviceFilter.unresponsive)
                Label("Disabled Integrations (\(viewModel.devicesFromDisabledIntegrations().count))", systemImage: "puzzlepiece.extension")
                    .tag(DeviceFilter.disabledIntegrations)
            }

            Section {
                ForEach(viewModel.groupedByDeviceGroup, id: \.group.id) { entry in
                    GroupRow(group: entry.group, count: entry.devices.count, viewModel: viewModel, selectedFilter: $selectedFilter)
                        .tag(DeviceFilter.group(entry.group.id))
                }
            } header: {
                HStack {
                    Text("Groups")
                    Spacer()
                    Button {
                        newGroupName = ""
                        isCreatingGroup = true
                    } label: {
                        Image(systemName: "plus.circle")
                    }
                    .buttonStyle(.plain)
                    .help("Create new group")
                }
            }

            Section("By Type") {
                ForEach(viewModel.groupedByType, id: \.type) { group in
                    Label("\(group.type) (\(group.devices.count))", systemImage: group.devices.first?.typeSymbolName ?? "cube")
                        .tag(DeviceFilter.type(group.type))
                }
            }

            Section("By Integration (Skill)") {
                ForEach(viewModel.groupedBySkill, id: \.skillId) { group in
                    IntegrationRow(skillId: group.skillId, count: group.devices.count, viewModel: viewModel, integrationStore: integrationStore)
                        .tag(DeviceFilter.skill(group.skillId))
                }
            }
        }
        .listStyle(.sidebar)
        .frame(minWidth: 280)
        .alert("New Group", isPresented: $isCreatingGroup) {
            TextField("Name", text: $newGroupName)
            Button("Create") {
                Task { await viewModel.createGroup(name: newGroupName) }
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}

private struct GroupRow: View {
    let group: DeviceGroup
    let count: Int
    @ObservedObject var viewModel: DeviceListViewModel
    /// The filter currently shown in the table - if that's a different
    /// group, a drop here is treated as a "move" (out of the source group,
    /// into this one) instead of a plain "add". A binding (not just `let`)
    /// so the view can jump straight to the destination group after a
    /// successful drop - otherwise the table doesn't show that the devices
    /// actually arrived (the mutation itself already works reliably, see
    /// the swiftui-list-drop-highlight memory).
    @Binding var selectedFilter: DeviceFilter
    @State private var isEditingName = false
    @State private var nameDraft = ""
    @State private var isConfirmingDelete = false
    @State private var isDropTargeted = false

    var body: some View {
        Label("\(group.name) (\(count))", systemImage: "rectangle.3.group")
            .listRowBackground(isDropTargeted ? Color.accentColor.opacity(0.25) : Color.clear)
            .contextMenu {
                Button("Rename…") {
                    nameDraft = group.name
                    isEditingName = true
                }
                Button("Delete…", role: .destructive) {
                    isConfirmingDelete = true
                }
            }
            .alert("Rename Group", isPresented: $isEditingName) {
                TextField("Name", text: $nameDraft)
                Button("Save") {
                    Task { await viewModel.renameGroup(group, to: nameDraft) }
                }
                Button("Cancel", role: .cancel) {}
            }
            .confirmationDialog(
                "Really delete group “\(group.name)”?",
                isPresented: $isConfirmingDelete,
                titleVisibility: .visible
            ) {
                Button("Delete", role: .destructive) {
                    Task { await viewModel.deleteGroup(group) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This action cannot be undone. The devices themselves will not be deleted.")
            }
            .dropDestination(for: String.self) { payloads, _ in
                let applianceIds = payloads.flatMap { DeviceDragPayload.decode($0) }
                let devices = applianceIds.compactMap { id in
                    viewModel.devices.first { $0.applianceId == id }
                }
                guard !devices.isEmpty else { return false }
                if case .group(let sourceGroupId) = selectedFilter,
                   sourceGroupId != group.id,
                   let sourceGroup = viewModel.deviceGroups.first(where: { $0.id == sourceGroupId }) {
                    Task { await viewModel.moveDevices(devices, fromGroup: sourceGroup, toGroup: group) }
                } else {
                    Task { await viewModel.addDevices(devices, toGroup: group) }
                }
                // Jump straight to the destination group so it's visible
                // that the devices arrived (the table otherwise doesn't
                // automatically follow the drop target).
                selectedFilter = .group(group.id)
                return true
            } isTargeted: { isDropTargeted = $0 }
    }
}

private struct IntegrationRow: View {
    let skillId: String
    let count: Int
    @ObservedObject var viewModel: DeviceListViewModel
    @ObservedObject var integrationStore: IntegrationStore
    @State private var isEditingName = false
    @State private var nameDraft = ""

    var body: some View {
        let meta = integrationStore.meta(for: skillId)
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(viewModel.integrationLabel(for: skillId))
                    .lineLimit(1)
                Text(skillId)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            Text("\(count)")
                .foregroundStyle(.secondary)
        }
        .contextMenu {
            Button("Edit Display Name…") {
                nameDraft = meta.displayName ?? ""
                isEditingName = true
            }
        }
        .alert("Display Name for Integration", isPresented: $isEditingName) {
            TextField("Name", text: $nameDraft)
            Button("Save") {
                integrationStore.setDisplayName(nameDraft, for: skillId)
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}
