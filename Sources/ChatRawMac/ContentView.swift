import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var backend: BackendController

    var body: some View {
        Group {
            switch backend.state {
            case .idle:
                StatusView(title: "ChatRaw for Mac", message: "Preparing...")
            case .starting(let message):
                StatusView(title: "ChatRaw for Mac", message: message, logs: backend.recentLogs)
            case .ready(let url):
                WebContainerView(url: url)
            case .failed(let message):
                StatusView(
                    title: "Backend failed",
                    message: message,
                    logs: backend.recentLogs,
                    retry: backend.start
                )
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

private struct StatusView: View {
    let title: String
    let message: String
    var logs: String = ""
    var retry: (() -> Void)?

    var body: some View {
        VStack(spacing: 18) {
            ProgressView()
                .controlSize(.large)
                .opacity(retry == nil ? 1 : 0)

            Text(title)
                .font(.title2.weight(.semibold))

            Text(message)
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .textSelection(.enabled)

            if let retry {
                Button("Retry", action: retry)
                    .keyboardShortcut(.defaultAction)
            }

            if !logs.isEmpty {
                ScrollView {
                    Text(logs)
                        .font(.system(.caption, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(12)
                }
                .frame(maxWidth: 760, maxHeight: 240)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
