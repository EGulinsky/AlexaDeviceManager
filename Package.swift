// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "AlexaDeviceManager",
    platforms: [
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "AlexaDeviceManager",
            path: "Sources/AlexaDeviceManager",
            resources: [
                .copy("Resources/Assets.xcassets")
            ]
        )
    ]
)
