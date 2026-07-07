import Foundation

/// SwiftUI's `Table` only allows a single sort-comparator type across all
/// columns per table - so this is one shared comparator for every column
/// instead of a `KeyPathComparator` just for the ones that access `Device`
/// properties directly.
///
/// An earlier version used a separately-passed-in label dictionary for
/// "Integration" (to sort by the displayed plain text instead of the raw
/// skill ID) - but that caused clicking the column header to toggle the
/// sort arrow while the row order never actually changed (confirmed via
/// live testing; root cause never fully pinned down - SwiftUI's Table
/// likely retains an older/empty comparator snapshot across the toggle).
/// Fix: `.integration` now sorts directly by `Device.integrationGroupKey`
/// (raw, no external dictionary needed) - matches the displayed text in
/// practically every case without a manually-set display name.
struct DeviceSortComparator: SortComparator {
    enum Field: Hashable {
        case name
        case type
        case integration
        case status
        case applianceId
    }

    var field: Field
    var order: SortOrder = .forward

    func compare(_ lhs: Device, _ rhs: Device) -> ComparisonResult {
        let result: ComparisonResult
        switch field {
        case .name:
            result = Self.compareStrings(lhs.friendlyName, rhs.friendlyName)
        case .type:
            result = Self.compareStrings(lhs.typeLabel, rhs.typeLabel)
        case .integration:
            result = Self.compareStrings(lhs.integrationGroupKey, rhs.integrationGroupKey)
        case .status:
            result = Self.compareStrings(lhs.connectivity.rawValue, rhs.connectivity.rawValue)
        case .applianceId:
            result = Self.compareStrings(lhs.applianceId, rhs.applianceId)
        }
        return order == .forward ? result : result.reversed
    }

    private static func compareStrings(_ a: String, _ b: String) -> ComparisonResult {
        a.localizedStandardCompare(b)
    }
}

private extension ComparisonResult {
    var reversed: ComparisonResult {
        switch self {
        case .orderedAscending: return .orderedDescending
        case .orderedDescending: return .orderedAscending
        case .orderedSame: return .orderedSame
        }
    }
}
