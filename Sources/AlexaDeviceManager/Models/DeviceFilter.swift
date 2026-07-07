import Foundation

enum DeviceFilter: Hashable {
    case all
    case skill(String)
    case type(String)
    case group(String)
    case unresponsive
    case disabledIntegrations
}

enum BatchAction: Identifiable {
    case selected([Device])
    case unresponsive
    case disabledIntegrations
    case all

    var id: String {
        switch self {
        case .selected: return "selected"
        case .unresponsive: return "unresponsive"
        case .disabledIntegrations: return "disabledIntegrations"
        case .all: return "all"
        }
    }
}
