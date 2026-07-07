import SwiftUI

struct ContentView: View {
    @StateObject private var session: AlexaWebSession
    @StateObject private var integrationStore: IntegrationStore
    @StateObject private var viewModel: DeviceListViewModel

    @State private var showLoginSheet = false
    @State private var selectedFilter: DeviceFilter = .all
    @State private var selectedIDs: Set<String> = []
    @State private var pendingBatchAction: BatchAction?
    @State private var schemaFieldsText: String?
    @State private var schemaFieldsError: String?

    init() {
        let session = AlexaWebSession()
        let store = IntegrationStore()
        _session = StateObject(wrappedValue: session)
        _integrationStore = StateObject(wrappedValue: store)
        _viewModel = StateObject(wrappedValue: DeviceListViewModel(session: session, integrationStore: store))
    }

    var body: some View {
        NavigationSplitView {
            IntegrationsSidebar(
                viewModel: viewModel,
                integrationStore: integrationStore,
                selectedFilter: $selectedFilter
            )
        } detail: {
            VStack(spacing: 0) {
                DeviceListView(devices: filteredDevices, selection: $selectedIDs, viewModel: viewModel)
                Divider()
                BatchActionsBar(
                    viewModel: viewModel,
                    selectedDevices: selectedDevices,
                    onSelectedDelete: { pendingBatchAction = .selected(selectedDevices) },
                    onUnresponsiveDelete: { pendingBatchAction = .unresponsive },
                    onDisabledIntegrationsDelete: { pendingBatchAction = .disabledIntegrations },
                    onDeleteAll: { pendingBatchAction = .all },
                    onAddSelected: { group in
                        let devices = selectedDevices
                        Task { await viewModel.addDevices(devices, toGroup: group) }
                    },
                    onRemoveSelected: { group in
                        let devices = selectedDevices
                        Task { await viewModel.removeDevices(devices, fromGroup: group) }
                    },
                    onCreateGroupFromSelection: { name in
                        let devices = selectedDevices
                        Task { await viewModel.createGroup(name: name, withMembers: devices) }
                    }
                )
            }
        }
        .toolbar {
            ToolbarItem {
                Button {
                    showLoginSheet = true
                } label: {
                    Label(
                        session.isLoggedIn ? "Signed in" : "Sign in",
                        systemImage: session.isLoggedIn ? "person.crop.circle.badge.checkmark" : "person.crop.circle.badge.exclamationmark"
                    )
                }
            }
            ToolbarItem {
                Button {
                    Task { await viewModel.refresh() }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .disabled(viewModel.isBusy)
            }
            ToolbarItem {
                Button {
                    Task { await fetchSchemaFields() }
                } label: {
                    Label("Check Fields", systemImage: "list.bullet.rectangle")
                }
                .disabled(!session.isLoggedIn)
            }
        }
        .sheet(isPresented: $showLoginSheet) {
            LoginSheet(session: session)
        }
        .sheet(isPresented: Binding(
            get: { schemaFieldsText != nil || schemaFieldsError != nil },
            set: { if !$0 { schemaFieldsText = nil; schemaFieldsError = nil } }
        )) {
            SchemaFieldsSheet(text: schemaFieldsText, error: schemaFieldsError) {
                schemaFieldsText = nil
                schemaFieldsError = nil
            }
        }
        .confirmationDialog(
            confirmationTitle,
            isPresented: Binding(
                get: { pendingBatchAction != nil },
                set: { if !$0 { pendingBatchAction = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                if let action = pendingBatchAction {
                    Task { await performBatchAction(action) }
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This action cannot be undone.")
        }
        .task {
            // Silently check persisted session cookies from previous
            // launches, without needing to open the login dialog for it.
            let alreadyLoggedIn = await session.attemptAutoLogin()
            if alreadyLoggedIn {
                await viewModel.refresh()
            } else {
                showLoginSheet = true
            }
        }
        // Otherwise IDs from the old filter view linger in `selectedIDs`
        // that no longer appear in the newly filtered `filteredDevices` -
        // this caused a drag & drop of a supposed multi-selection to only
        // deliver part of the devices at the target (the IDs from the old
        // view could no longer be mapped to a `Device`).
        .onChange(of: selectedFilter) { _, _ in
            selectedIDs.removeAll()
        }
        .frame(minWidth: 900, minHeight: 600)
    }

    private var filteredDevices: [Device] {
        switch selectedFilter {
        case .all:
            return viewModel.devices
        case .skill(let skillId):
            // Devices without a recognizable skill ID are grouped by their
            // manufacturer name (see `Device.integrationGroupKey`) - the
            // same logic as in `groupedBySkill` has to apply here, or no
            // device would match.
            return viewModel.devices.filter { $0.integrationGroupKey == skillId }
        case .type(let type):
            return viewModel.devices.filter { $0.typeLabel == type }
        case .group(let groupId):
            return viewModel.devicesInGroup(groupId)
        case .unresponsive:
            return viewModel.unresponsiveDevices()
        case .disabledIntegrations:
            return viewModel.devicesFromDisabledIntegrations()
        }
    }

    private var selectedDevices: [Device] {
        viewModel.devices.filter { selectedIDs.contains($0.id) }
    }

    private func targetDevices(for action: BatchAction) -> [Device] {
        switch action {
        case .selected(let devices): return devices
        case .unresponsive: return viewModel.unresponsiveDevices()
        case .disabledIntegrations: return viewModel.devicesFromDisabledIntegrations()
        case .all: return viewModel.devices
        }
    }

    private var confirmationTitle: String {
        guard let action = pendingBatchAction else { return "" }
        return "Really delete \(targetDevices(for: action).count) device(s)?"
    }

    private func performBatchAction(_ action: BatchAction) async {
        let target = targetDevices(for: action)
        pendingBatchAction = nil
        await viewModel.delete(target)
        selectedIDs.removeAll()
    }

    private func fetchSchemaFields() async {
        do {
            schemaFieldsText = try await session.fetchAllEndpointFieldNames()
        } catch {
            schemaFieldsError = error.localizedDescription
        }
    }
}

private struct SchemaFieldsSheet: View {
    let text: String?
    let error: String?
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Available Endpoint Fields (GraphQL Introspection)")
                .font(.headline)

            ScrollView {
                Text(text ?? error ?? "")
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(error != nil ? .red : .primary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack {
                Spacer()
                Button("Done", action: onDismiss)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding()
        .frame(minWidth: 500, minHeight: 400)
    }
}
