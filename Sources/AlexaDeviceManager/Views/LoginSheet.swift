import SwiftUI

struct LoginSheet: View {
    @ObservedObject var session: AlexaWebSession
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Picker("Region", selection: $session.region) {
                    ForEach(AlexaRegion.candidates) { region in
                        Text(region.label).tag(region)
                    }
                }
                .frame(maxWidth: 280)

                Button("1. Sign in with Amazon") {
                    session.loadSignInPage()
                }

                Button("2. Load Alexa") {
                    session.loadAlexaHost()
                }

                Button("Check Sign-In") {
                    Task { await session.checkLoginStatus() }
                }

                Spacer()

                if session.isLoading {
                    ProgressView().controlSize(.small)
                }

                statusBadge

                Button("Done") { dismiss() }
                    .keyboardShortcut(.defaultAction)
            }
            .padding()

            Text("First use “Sign in with Amazon” - this opens the Amazon homepage. Click “Sign in” in the top right there and log in normally with email/password (+ 2FA). Then tap “Load Alexa” to pick up the session.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal)
                .frame(maxWidth: .infinity, alignment: .leading)

            if let url = session.currentURL {
                Text("Current URL: \(url)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            if let error = session.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .padding(.horizontal)
                    .padding(.bottom, 4)
            }

            Divider()

            WebViewRepresentable(webView: session.webView)
        }
        .frame(minWidth: 700, minHeight: 600)
        .onAppear {
            if !session.isLoggedIn {
                session.loadSignInPage()
            }
        }
    }

    @ViewBuilder
    private var statusBadge: some View {
        if session.isLoggedIn {
            Label("Signed In", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        } else {
            Label("Not Signed In", systemImage: "xmark.circle")
                .foregroundStyle(.secondary)
        }
    }
}
