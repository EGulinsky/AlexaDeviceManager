import Foundation

struct AlexaRegion: Identifiable, Hashable {
    let id: String // Alexa host
    let label: String
    /// Amazon's main domain where the actual sign-in (email/password/2FA)
    /// happens. `alexa.<tld>` itself now only shows the QR code splash for
    /// pairing the phone app - but the session cookie from the main domain
    /// is also valid for the Alexa subdomain (same root domain).
    let retailDomain: String

    var baseURL: URL { URL(string: "https://\(id)")! }
    /// Hitting `/ap/signin` directly returns a 404 without the right openid
    /// query parameters - the homepage links there correctly, so we load
    /// the homepage instead and let the user click "Sign in" themselves.
    var signInURL: URL { URL(string: "https://www.\(retailDomain)/")! }

    static let candidates: [AlexaRegion] = [
        AlexaRegion(id: "alexa.amazon.de", label: "Germany (alexa.amazon.de)", retailDomain: "amazon.de"),
        AlexaRegion(id: "alexa.amazon.com", label: "USA (alexa.amazon.com)", retailDomain: "amazon.com"),
        AlexaRegion(id: "pitangui.amazon.com", label: "USA – Pitangui (pitangui.amazon.com)", retailDomain: "amazon.com"),
        AlexaRegion(id: "layla.amazon.com", label: "EU/UK (layla.amazon.com)", retailDomain: "amazon.co.uk"),
        AlexaRegion(id: "alexa.amazon.co.jp", label: "Japan (alexa.amazon.co.jp)", retailDomain: "amazon.co.jp")
    ]
}
