// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "ChatRawMac",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "ChatRawMac", targets: ["ChatRawMac"])
    ],
    targets: [
        .executableTarget(
            name: "ChatRawMac",
            exclude: ["Resources"]
        )
    ]
)
