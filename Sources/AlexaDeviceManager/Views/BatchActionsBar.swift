import SwiftUI

struct BatchActionsBar: View {
    @ObservedObject var viewModel: DeviceListViewModel
    let selectedDevices: [Device]
    let onSelectedDelete: () -> Void
    let onUnresponsiveDelete: () -> Void
    let onDisabledIntegrationsDelete: () -> Void
    let onDeleteAll: () -> Void
    let onAddSelected: (DeviceGroup) -> Void
    let onRemoveSelected: (DeviceGroup) -> Void
    let onCreateGroupFromSelection: (String) -> Void

    @State private var isCreatingGroupFromSelection = false
    @State private var newGroupName = ""

    private var selectedCount: Int { selectedDevices.count }

    var body: some View {
        VStack(spacing: 4) {
            if let progress = viewModel.progress {
                ProgressView(value: Double(progress.done), total: Double(progress.total)) {
                    Text("Deleting \(progress.done)/\(progress.total)…")
                        .font(.caption)
                }
            } else if let message = viewModel.statusMessage {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack {
                Button("Delete Selected (\(selectedCount))", action: onSelectedDelete)
                    .disabled(selectedCount == 0 || viewModel.isBusy)

                Button("Delete Not Responding (\(viewModel.unresponsiveDevices().count))", action: onUnresponsiveDelete)
                    .disabled(viewModel.unresponsiveDevices().isEmpty || viewModel.isBusy)

                Button("Delete Disabled Integrations (\(viewModel.devicesFromDisabledIntegrations().count))", action: onDisabledIntegrationsDelete)
                    .disabled(viewModel.devicesFromDisabledIntegrations().isEmpty || viewModel.isBusy)

                Menu("Groups (\(selectedCount))") {
                    Menu("Add to Group") {
                        if viewModel.deviceGroups.isEmpty {
                            Text("No groups yet")
                        }
                        ForEach(viewModel.deviceGroups) { group in
                            Button(group.name) { onAddSelected(group) }
                        }
                    }
                    Menu("Remove from Group") {
                        if viewModel.deviceGroups.isEmpty {
                            Text("No groups yet")
                        }
                        ForEach(viewModel.deviceGroups) { group in
                            Button(group.name) { onRemoveSelected(group) }
                        }
                    }
                    Button("New Group from Selection…") {
                        newGroupName = ""
                        isCreatingGroupFromSelection = true
                    }
                }
                .disabled(selectedCount == 0 || viewModel.isBusy)

                Spacer()

                Button("Delete All (\(viewModel.devices.count))", role: .destructive, action: onDeleteAll)
                    .disabled(viewModel.devices.isEmpty || viewModel.isBusy)
            }
        }
        .padding(8)
        .alert("New Group from \(selectedCount) Device(s)", isPresented: $isCreatingGroupFromSelection) {
            TextField("Name", text: $newGroupName)
            Button("Create") { onCreateGroupFromSelection(newGroupName) }
            Button("Cancel", role: .cancel) {}
        }
    }
}
