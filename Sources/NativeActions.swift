import Foundation
import UIKit
import WebKit

@MainActor
enum NativeActions {
    static func toggleOrientation() {
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()

        guard let scene = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .first(where: { $0.activationState == .foregroundActive }) else {
            return
        }

        let wantsLandscape = scene.interfaceOrientation.isPortrait

        if #available(iOS 16.0, *) {
            let preferences = UIWindowScene.GeometryPreferences.iOS(
                interfaceOrientations: wantsLandscape ? .landscape : .portrait
            )
            scene.requestGeometryUpdate(preferences) { error in
                print("Dexter orientation update failed: \(error.localizedDescription)")
            }
            scene.keyWindow?.rootViewController?.setNeedsUpdateOfSupportedInterfaceOrientations()
        } else {
            let value = wantsLandscape
                ? UIInterfaceOrientation.landscapeRight.rawValue
                : UIInterfaceOrientation.portrait.rawValue
            UIDevice.current.setValue(value, forKey: "orientation")
            UIViewController.attemptRotationToDeviceOrientation()
        }
    }

    static func downloadMedia(
        directURL: URL?,
        mediaURL: URL?,
        from webView: WKWebView?,
        status: @escaping (String?) -> Void
    ) {
        let candidate = directURL ?? mediaURL
        guard let url = candidate,
              let scheme = url.scheme?.lowercased(),
              ["http", "https"].contains(scheme) else {
            showAlert(
                title: "Download unavailable",
                message: "Dexter did not expose a downloadable file for this title."
            )
            return
        }

        let extensionName = url.pathExtension.lowercased()
        let directFileExtensions = ["mp4", "m4v", "mov", "mkv", "webm"]
        guard directFileExtensions.contains(extensionName) || directURL != nil else {
            showAlert(
                title: "Streaming source",
                message: "This title is being delivered as a streaming playlist rather than a single downloadable file. The download button will work automatically whenever Dexter exposes a direct media file."
            )
            return
        }

        status("Preparing download…")
        UINotificationFeedbackGenerator().notificationOccurred(.success)

        let beginDownload: ([HTTPCookie]) -> Void = { cookies in
            var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 60)
            request.setValue(webView?.url?.absoluteString ?? "https://dexter.pw/", forHTTPHeaderField: "Referer")

            if !cookies.isEmpty {
                let fields = HTTPCookie.requestHeaderFields(with: cookies)
                fields.forEach { request.setValue($1, forHTTPHeaderField: $0) }
            }

            URLSession.shared.downloadTask(with: request) { temporaryURL, response, error in
                DispatchQueue.main.async {
                    status(nil)

                    if let error {
                        showAlert(title: "Download failed", message: error.localizedDescription)
                        return
                    }

                    guard let temporaryURL else {
                        showAlert(title: "Download failed", message: "The server did not return a media file.")
                        return
                    }

                    do {
                        let fileManager = FileManager.default
                        let downloads = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
                            .appendingPathComponent("Dexter Downloads", isDirectory: true)
                        try fileManager.createDirectory(at: downloads, withIntermediateDirectories: true)

                        var name = response?.suggestedFilename
                            ?? url.lastPathComponent.removingPercentEncoding
                            ?? "Dexter-Video.\(extensionName.isEmpty ? "mp4" : extensionName)"
                        if name.isEmpty {
                            name = "Dexter-Video.\(extensionName.isEmpty ? "mp4" : extensionName)"
                        }

                        var destination = downloads.appendingPathComponent(name)
                        if fileManager.fileExists(atPath: destination.path) {
                            let stem = destination.deletingPathExtension().lastPathComponent
                            let ext = destination.pathExtension
                            let replacement = "\(stem)-\(Int(Date().timeIntervalSince1970))\(ext.isEmpty ? "" : ".\(ext)")"
                            destination = downloads.appendingPathComponent(replacement)
                        }

                        try fileManager.moveItem(at: temporaryURL, to: destination)
                        presentShareSheet(fileURL: destination)
                    } catch {
                        showAlert(title: "Download failed", message: error.localizedDescription)
                    }
                }
            }.resume()
        }

        if let webView {
            webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { cookies in
                beginDownload(cookies)
            }
        } else {
            beginDownload([])
        }
    }

    private static func presentShareSheet(fileURL: URL) {
        guard let presenter = topViewController() else { return }
        let controller = UIActivityViewController(activityItems: [fileURL], applicationActivities: nil)
        if let popover = controller.popoverPresentationController {
            popover.sourceView = presenter.view
            popover.sourceRect = CGRect(x: presenter.view.bounds.midX, y: presenter.view.bounds.maxY - 40, width: 1, height: 1)
        }
        presenter.present(controller, animated: true)
    }

    static func showAlert(title: String, message: String) {
        guard let presenter = topViewController() else { return }
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        presenter.present(alert, animated: true)
    }

    private static func topViewController() -> UIViewController? {
        guard let scene = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .first(where: { $0.activationState == .foregroundActive }),
              let root = scene.windows.first(where: { $0.isKeyWindow })?.rootViewController else {
            return nil
        }

        var current = root
        while let presented = current.presentedViewController {
            current = presented
        }
        return current
    }
}

private extension UIWindowScene {
    var keyWindow: UIWindow? {
        windows.first(where: { $0.isKeyWindow })
    }
}
