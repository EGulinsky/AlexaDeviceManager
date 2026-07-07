import Foundation

/// Drag & drop payload for one or more device rows from the table - bundles
/// applianceIds so a multi-selection can also be dragged in a single
/// gesture (a single `.draggable(String)` with just one applianceId always
/// only carries the one row under the cursor, see `DeviceListView`).
///
/// Deliberately encoded as a plain `String` (not a custom `Transferable`
/// type with its own `UTType`) - a first attempt with
/// `CodableRepresentation(contentType: custom UTType(exportedAs:))`
/// completely broke drag & drop (no drop possible at all, even after
/// several debugging attempts around hover highlighting/hit area). A single
/// `.draggable(String)` demonstrably worked, though - so multiple IDs are
/// simply packed line-by-line into a String here, using SwiftUI's built-in
/// Transferable conformance.
enum DeviceDragPayload {
    private static let separator = "\n"

    static func encode(_ applianceIds: [String]) -> String {
        applianceIds.joined(separator: separator)
    }

    static func decode(_ payload: String) -> [String] {
        payload.components(separatedBy: separator).filter { !$0.isEmpty }
    }
}
