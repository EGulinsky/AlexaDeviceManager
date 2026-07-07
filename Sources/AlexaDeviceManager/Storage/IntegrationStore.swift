import Foundation

struct IntegrationMeta: Codable, Equatable {
    var displayName: String?
}

/// `manufacturer.value.text` already provides a readable name for most
/// endpoints (see AlexaWebSession.fetchDevices), but not for all - for the
/// remaining cases a display name can be stored locally here.
@MainActor
final class IntegrationStore: ObservableObject {
    @Published private(set) var meta: [String: IntegrationMeta] = [:]

    private let fileURL: URL

    init() {
        let supportDir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let appDir = supportDir.appendingPathComponent("AlexaDeviceManager", isDirectory: true)
        try? FileManager.default.createDirectory(at: appDir, withIntermediateDirectories: true)
        fileURL = appDir.appendingPathComponent("integrations.json")
        load()
    }

    func meta(for skillId: String) -> IntegrationMeta {
        meta[skillId] ?? IntegrationMeta()
    }

    /// Amazon doesn't provide a display name for skills via the API -
    /// without a manually set name, we show a shortened, more readable form
    /// of the skill ID instead of the full `amzn1.ask.skill.<uuid>` string.
    func label(for skillId: String) -> String {
        if let name = meta(for: skillId).displayName {
            return name
        }
        if let lastComponent = skillId.split(separator: ".").last {
            return "Skill …\(lastComponent.suffix(8))"
        }
        return skillId
    }

    func setDisplayName(_ name: String?, for skillId: String) {
        var m = meta(for: skillId)
        m.displayName = (name?.isEmpty ?? true) ? nil : name
        meta[skillId] = m
        save()
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([String: IntegrationMeta].self, from: data) else {
            return
        }
        meta = decoded
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(meta) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
