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

    weak var webView: WKWebView?

    func attach(_ webView: WKWebView) {
        self.webView = webView
        updateNavigationState()
    }

    func updateNavigationState() {
        guard let webView else { return }
        canGoBack = webView.canGoBack
        canGoForward = webView.canGoForward
    }

    func beginLoading() {
        isLoading = true
        errorMessage = nil
    }

    func finishLoading(title: String?) {
        isLoading = false
        progress = 1
        hasLoadedOnce = true
        errorMessage = nil
        if let title, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            pageTitle = title
        }
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
}
