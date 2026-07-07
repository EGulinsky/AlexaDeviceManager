import Foundation

/// Alexa "Group" as returned by the `listDeviceGroups` query (verified via
/// introspection, see the alexa_graphql_schema memory). `memberEndpointIds`
/// holds the internal endpoint `id` of member devices (NOT
/// `legacyAppliance.applianceId` - that's `null` for native Amazon devices
/// like Sonos/Echo, see `Device.endpointId`).
struct DeviceGroup: Identifiable, Hashable {
    let id: String
    let name: String
    let memberEndpointIds: Set<String>
}

/// Values of `CollectionOperationOptions` (confirmed via introspection: ADD,
/// REMOVE, REPLACE) - controls how `memberDeviceIds` is interpreted in
/// `updateDeviceGroup`.
enum DeviceGroupMemberOperation: String {
    case add = "ADD"
    case remove = "REMOVE"
    case replace = "REPLACE"
}
