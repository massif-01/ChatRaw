import Combine
import Darwin
import Foundation

enum BackendState: Equatable {
    case idle
    case starting(String)
    case ready(URL)
    case failed(String)
}

final class BackendController: ObservableObject, @unchecked Sendable {
    @Published private(set) var state: BackendState = .idle
    @Published private(set) var recentLogs: String = ""

    private var process: Process?
    private var pipe: Pipe?
    private var currentPort: Int?
    private var didStart = false
    private let logQueue = DispatchQueue(label: "com.massif.ChatRawMac.backend-logs")
    private var logLines: [String] = []

    deinit {
        stop()
    }

    func startIfNeeded() {
        guard !didStart else { return }
        didStart = true
        start()
    }

    func start() {
        stop()
        setState(.starting("Starting ChatRaw backend..."))

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.launchBackend()
        }
    }

    func stop() {
        pipe?.fileHandleForReading.readabilityHandler = nil
        pipe = nil

        guard let process else { return }
        process.terminationHandler = nil
        if process.isRunning {
            process.terminate()
        }
        self.process = nil
        currentPort = nil
    }

    private func launchBackend() {
        do {
            let runtime = try resolveBackendRuntime()

            let port = try findAvailablePort()
            currentPort = port
            writeStatus("starting", port: port)

            let dataDir = try applicationDataDirectory()
            try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)

            let outputPipe = Pipe()
            pipe = outputPipe
            outputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                let text = String(data: data, encoding: .utf8) ?? String(decoding: data, as: UTF8.self)
                self?.appendLog(text)
            }

            let process = Process()
            process.executableURL = runtime.executableURL
            process.currentDirectoryURL = runtime.rootURL
            process.arguments = runtime.arguments(host: "127.0.0.1", port: port)

            var environment = ProcessInfo.processInfo.environment
            environment["DATA_DIR"] = dataDir.path
            environment["PYTHONUNBUFFERED"] = "1"
            process.environment = environment
            process.standardOutput = outputPipe
            process.standardError = outputPipe
            process.terminationHandler = { [weak self] terminated in
                guard terminated.terminationStatus != 0 else { return }
                self?.setState(.failed("Backend exited with status \(terminated.terminationStatus)."))
            }

            self.process = process
            try process.run()

            let baseURL = URL(string: "http://127.0.0.1:\(port)/")!
            pollReady(baseURL: baseURL, remainingAttempts: 80)
        } catch {
            setState(.failed(error.localizedDescription))
        }
    }

    private func pollReady(baseURL: URL, remainingAttempts: Int) {
        guard remainingAttempts > 0 else {
            setState(.failed("Backend did not become ready in time."))
            return
        }

        let readyURL = baseURL.appendingPathComponent("ready")
        URLSession.shared.dataTask(with: readyURL) { [weak self] _, response, _ in
            guard let self else { return }

            if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                self.setState(.ready(baseURL))
                return
            }

            let nextAttempt = remainingAttempts - 1
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 0.25) {
                self.pollReady(baseURL: baseURL, remainingAttempts: nextAttempt)
            }
        }.resume()
    }

    private func appendLog(_ text: String) {
        logQueue.async { [weak self] in
            guard let self else { return }
            let newLines = text.components(separatedBy: .newlines).filter { !$0.isEmpty }
            self.logLines.append(contentsOf: newLines)
            if self.logLines.count > 200 {
                self.logLines.removeFirst(self.logLines.count - 200)
            }
            let joined = self.logLines.joined(separator: "\n")
            DispatchQueue.main.async {
                self.recentLogs = joined
            }
        }
    }

    private func setState(_ state: BackendState) {
        switch state {
        case .ready(let url):
            writeStatus("ready", port: currentPort, url: url)
        case .failed(let message):
            writeStatus("failed", port: currentPort, message: message)
        case .starting:
            writeStatus("starting", port: currentPort)
        case .idle:
            writeStatus("idle", port: currentPort)
        }

        DispatchQueue.main.async {
            self.state = state
        }
    }

    private func resolveBackendRuntime() throws -> BackendRuntime {
        let fileManager = FileManager.default

        if let explicitRoot = ProcessInfo.processInfo.environment["CHATRAW_REPO_ROOT"], !explicitRoot.isEmpty {
            let url = URL(fileURLWithPath: explicitRoot)
            if let runtime = pythonBackendRuntime(in: url) { return runtime }
        }

        if let resourcesURL = Bundle.main.resourceURL,
           let runtime = bundledBackendRuntime(in: resourcesURL) ?? pythonBackendRuntime(in: resourcesURL) {
            return runtime
        }

        let bundleURL = Bundle.main.bundleURL
        let devBundleRoot = bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        if let runtime = pythonBackendRuntime(in: devBundleRoot) {
            return runtime
        }

        var current = URL(fileURLWithPath: fileManager.currentDirectoryPath)
        for _ in 0..<6 {
            if let runtime = pythonBackendRuntime(in: current) { return runtime }
            current.deleteLastPathComponent()
        }

        throw BackendError.repoRootNotFound
    }

    private func bundledBackendRuntime(in resourcesURL: URL) -> BackendRuntime? {
        let executableURL = resourcesURL.appendingPathComponent("ChatRawBackend/ChatRawBackend")
        guard FileManager.default.isExecutableFile(atPath: executableURL.path) else {
            return nil
        }
        return BackendRuntime(
            rootURL: executableURL.deletingLastPathComponent(),
            executableURL: executableURL,
            launchKind: .bundledExecutable
        )
    }

    private func pythonBackendRuntime(in root: URL) -> BackendRuntime? {
        let fileManager = FileManager.default
        let backendPath = root.appendingPathComponent("backend/main.py").path
        let pythonURL = root.appendingPathComponent("venv/bin/python")
        guard fileManager.fileExists(atPath: backendPath),
              fileManager.isExecutableFile(atPath: pythonURL.path) else {
            return nil
        }
        return BackendRuntime(
            rootURL: root,
            executableURL: pythonURL,
            launchKind: .pythonModule
        )
    }

    private func applicationDataDirectory() throws -> URL {
        try applicationSupportDirectory()
            .appendingPathComponent("data", isDirectory: true)
    }

    private func applicationSupportDirectory() throws -> URL {
        guard let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            throw BackendError.dataDirectoryUnavailable
        }
        return support
            .appendingPathComponent("ChatRawMac", isDirectory: true)
    }

    private func writeStatus(_ state: String, port: Int? = nil, message: String? = nil, url: URL? = nil) {
        do {
            let directory = try applicationSupportDirectory()
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

            var payload: [String: Any] = [
                "state": state,
                "updated_at": ISO8601DateFormatter().string(from: Date())
            ]
            if let port {
                payload["port"] = port
            }
            if let message {
                payload["message"] = message
            }
            if let url {
                payload["url"] = url.absoluteString
            }

            let data = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: directory.appendingPathComponent("backend-status.json"), options: .atomic)
        } catch {
            appendLog("Failed to write backend status: \(error.localizedDescription)")
        }
    }

    private func findAvailablePort() throws -> Int {
        let socketDescriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard socketDescriptor >= 0 else {
            throw BackendError.portUnavailable
        }
        defer { close(socketDescriptor) }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(0).bigEndian
        address.sin_addr = in_addr(s_addr: in_addr_t(INADDR_LOOPBACK).bigEndian)

        let bindResult = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                bind(socketDescriptor, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bindResult == 0 else {
            throw BackendError.portUnavailable
        }

        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let nameResult = withUnsafeMutablePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                getsockname(socketDescriptor, sockaddrPointer, &length)
            }
        }
        guard nameResult == 0 else {
            throw BackendError.portUnavailable
        }

        return Int(UInt16(bigEndian: address.sin_port))
    }
}

private struct BackendRuntime {
    let rootURL: URL
    let executableURL: URL
    let launchKind: LaunchKind

    func arguments(host: String, port: Int) -> [String] {
        switch launchKind {
        case .bundledExecutable:
            return ["--host", host, "--port", String(port)]
        case .pythonModule:
            return [
                "-m", "uvicorn",
                "backend.main:app",
                "--host", host,
                "--port", String(port)
            ]
        }
    }
}

private enum LaunchKind {
    case bundledExecutable
    case pythonModule
}

private enum BackendError: LocalizedError {
    case repoRootNotFound
    case missingPython(String)
    case dataDirectoryUnavailable
    case portUnavailable

    var errorDescription: String? {
        switch self {
        case .repoRootNotFound:
            return "Could not locate the ChatRaw repository root."
        case .missingPython(let message):
            return message
        case .dataDirectoryUnavailable:
            return "Could not locate the macOS Application Support directory."
        case .portUnavailable:
            return "Could not allocate a local backend port."
        }
    }
}
