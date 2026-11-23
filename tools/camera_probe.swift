// Asks the iPhone, through macOS Image Capture, whether this Mac is allowed to
// delete camera roll items. Read-only: it never sends a delete request.
//
// Build and run:
//   swiftc -swift-version 5 tools/camera_probe.swift -o out/camera_probe && out/camera_probe

import Foundation
import ImageCaptureCore

final class Probe: NSObject, ICDeviceBrowserDelegate, ICCameraDeviceDelegate {
    let browser = ICDeviceBrowser()
    var camera: ICCameraDevice?

    func start() {
        browser.delegate = self
        let mask = ICDeviceTypeMask.camera.rawValue | ICDeviceLocationTypeMask.local.rawValue
        browser.browsedDeviceTypeMask = ICDeviceTypeMask(rawValue: mask) ?? .camera
        browser.start()
    }

    func report(_ device: ICCameraDevice) {
        let caps = device.capabilities
        print("items listed:        \(device.mediaFiles?.count ?? 0)")
        print("can delete one file: \(caps.contains(ICDeviceCapability.cameraDeviceCanDeleteOneFile.rawValue))")
        print("can delete all:      \(caps.contains(ICDeviceCapability.cameraDeviceCanDeleteAllFiles.rawValue))")
        print("iCloud Photos on:    \(device.iCloudPhotosEnabled)")
        print("phone locked:        \(device.isAccessRestrictedAppleDevice)")
    }

    // Browser
    func deviceBrowser(_ browser: ICDeviceBrowser, didAdd device: ICDevice, moreComing: Bool) {
        guard camera == nil, let found = device as? ICCameraDevice else { return }
        print("found:               \(device.name ?? "unnamed") (\(device.transportType ?? "?"))")
        camera = found
        found.delegate = self
        found.requestOpenSession()
    }
    func deviceBrowser(_ browser: ICDeviceBrowser, didRemove device: ICDevice, moreGoing: Bool) {}

    // Session
    func device(_ device: ICDevice, didOpenSessionWithError error: Error?) {
        if let error = error {
            print("session error:       \(error.localizedDescription)")
            exit(1)
        }
    }
    func device(_ device: ICDevice, didCloseSessionWithError error: Error?) {}
    func didRemove(_ device: ICDevice) {}

    // Camera
    func deviceDidBecomeReady(withCompleteContentCatalog device: ICCameraDevice) {
        report(device)
        exit(0)
    }
    func cameraDevice(_ camera: ICCameraDevice, didAdd items: [ICCameraItem]) {}
    func cameraDevice(_ camera: ICCameraDevice, didRemove items: [ICCameraItem]) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceiveThumbnail thumbnail: CGImage?, for item: ICCameraItem, error: Error?) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceiveMetadata metadata: [AnyHashable: Any]?, for item: ICCameraItem, error: Error?) {}
    func cameraDevice(_ camera: ICCameraDevice, didRenameItems items: [ICCameraItem]) {}
    func cameraDeviceDidChangeCapability(_ camera: ICCameraDevice) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceivePTPEvent eventData: Data) {}
    func cameraDeviceDidRemoveAccessRestriction(_ device: ICDevice) {}
    func cameraDeviceDidEnableAccessRestriction(_ device: ICDevice) {
        print("phone is locked — unlock it and run again")
    }
}

let probe = Probe()
probe.start()
DispatchQueue.main.asyncAfter(deadline: .now() + 90) {
    if let camera = probe.camera {
        print("timed out at \(camera.contentCatalogPercentCompleted)% of the catalog")
        probe.report(camera)
    } else {
        print("no camera device appeared")
    }
    exit(2)
}
RunLoop.main.run()
