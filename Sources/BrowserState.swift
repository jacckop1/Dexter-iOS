import Foundation
import WebKit

final class BrowserState: ObservableObject {
    let homeURL = URL(string: "https://dexter.pw")!

    @Published var progress: Double = 0
    @Published var isLoading = true
    @Published var canGoBack = false
    @Published var canGoForward = false
    @Published var hasLoadedOnce = false
    @Published var errorMessage: String?
    @Published var pageTitle = "Dexter"
    @Published var currentURL: URL?
    @Published var isPlayerPage = false
    @Published var mediaURL: URL?
    @Published var directDownloadURL: URL?
    @Published var subtitleTrackCount = 0
    @Published var nativeStatus: String?

    weak var webView: WKWebView?

    func attach(_ webView: WKWebView) {
        self.webView = webView
        updateNavigationState()
        updatePage(url: webView.url, title: webView.title)
    }

    func updateNavigationState() {
        guard let webView else { return }
        canGoBack = webView.canGoBack
        canGoForward = webView.canGoForward
    }

    func updatePage(url: URL?, title: String?) {
        if let url {
            currentURL = url
            isPlayerPage = url.path.hasPrefix("/watch/") || url.path == "/watch"
            if !isPlayerPage {
                mediaURL = nil
                directDownloadURL = nil
                subtitleTrackCount = 0
            }
        }

        if let title, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            pageTitle = title
        }
    }

    func updateMedia(src: String?, directDownload: String?, subtitleCount: Int) {
        if let src, let url = URL(string: src), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
            mediaURL = url
        }

        if let directDownload,
           let url = URL(string: directDownload),
           ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
            directDownloadURL = url
        } else {
            directDownloadURL = nil
        }

        subtitleTrackCount = max(0, subtitleCount)
    }

    func beginLoading(url: URL? = nil) {
        isLoading = true
        errorMessage = nil
        if let url {
            updatePage(url: url, title: nil)
        }
    }

    func finishLoading(url: URL?, title: String?) {
        isLoading = false
        progress = 1
        hasLoadedOnce = true
        errorMessage = nil
        updatePage(url: url, title: title)
        updateNavigationState()
    }

    func failLoading(_ message: String) {
        isLoading = false
        errorMessage = message
        updateNavigationState()
    }

    func goBack() {
        if webView?.canGoBack == true {
            webView?.goBack()
        }
    }

    func goForward() {
        if webView?.canGoForward == true {
            webView?.goForward()
        }
    }

    func reload() {
        errorMessage = nil
        if webView?.url == nil {
            loadHome()
        } else {
            webView?.reload()
        }
    }

    func loadHome() {
        errorMessage = nil
        let request = URLRequest(
            url: homeURL,
            cachePolicy: .useProtocolCachePolicy,
            timeoutInterval: 35
        )
        webView?.load(request)
    }

    func rotatePlayer() {
        NativeActions.toggleOrientation()
    }

    func downloadCurrentMedia() {
        NativeActions.downloadMedia(
            directURL: directDownloadURL,
            mediaURL: mediaURL,
            from: webView
        ) { [weak self] status in
            self?.nativeStatus = status
        }
    }
}
