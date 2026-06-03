import SwiftUI

@main
struct ChatRawMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var backend = BackendController()

    var body: some Scene {
        WindowGroup("ChatRaw for Mac") {
            ContentView()
                .environmentObject(backend)
                .frame(minWidth: 980, minHeight: 680)
                .onAppear {
                    appDelegate.backend = backend
                    backend.startIfNeeded()
                }
        }
        .windowStyle(.titleBar)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var backend: BackendController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationWillTerminate(_ notification: Notification) {
        backend?.stop()
    }
}
