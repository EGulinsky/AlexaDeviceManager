import Foundation

struct DecodedApplianceID: Hashable {
    let skillId: String
    let stage: String?
    let domain: String
    let objectId: String
}

enum ApplianceIDParser {
    private static let regex: NSRegularExpression = {
        try! NSRegularExpression(pattern: "^SKILL_([A-Za-z0-9+/=]+)_(.+)$")
    }()

    /// Decodes applianceIds in the format `SKILL_<base64-json>_<domain>#<object_id>`.
    /// Other skill types / native Amazon devices don't match this format -> nil.
    static func decode(_ applianceId: String) -> DecodedApplianceID? {
        let fullRange = NSRange(applianceId.startIndex..., in: applianceId)
        guard let match = regex.firstMatch(in: applianceId, range: fullRange),
              let base64Range = Range(match.range(at: 1), in: applianceId),
              let suffixRange = Range(match.range(at: 2), in: applianceId) else {
            return nil
        }

        let base64Part = String(applianceId[base64Range])
        let suffix = String(applianceId[suffixRange])

        guard let jsonData = Data(base64Encoded: base64Part),
              let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: String],
              let skillId = json["skillId"] else {
            return nil
        }

        let domainSplit = suffix.split(separator: "#", maxSplits: 1)
        let domain = domainSplit.first.map(String.init) ?? suffix
        let objectId = domainSplit.count > 1 ? String(domainSplit[1]) : ""

        return DecodedApplianceID(skillId: skillId, stage: json["stage"], domain: domain, objectId: objectId)
    }
}
