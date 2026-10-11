import SwiftUI
import WebKit
import UIKit

struct DexterWebView: UIViewRepresentable {
    @ObservedObject var state: BrowserState

    func makeCoordinator() -> Coordinator {
        Coordinator(state: state)
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.allowsAirPlayForMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.applicationNameForUserAgent = "Dexter-iOS/1.0"

        let userContentController = WKUserContentController()
        userContentController.addUserScript(
            WKUserScript(
                source: Self.polishScript,
                injectionTime: .atDocumentEnd,
                forMainFrameOnly: false
            )
        )
        configuration.userContentController = userContentController

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.allowsLinkPreview = false
        webView.isOpaque = false
        webView.backgroundColor = UIColor(red: 0.018, green: 0.018, blue: 0.025, alpha: 1)
        webView.scrollView.backgroundColor = webView.backgroundColor
        webView.scrollView.keyboardDismissMode = .interactive
        webView.scrollView.decelerationRate = .normal

        let refresh = UIRefreshControl()
        refresh.tintColor = UIColor(white: 0.72, alpha: 1)
        refresh.addTarget(context.coordinator, action: #selector(Coordinator.refresh(_:)), for: .valueChanged)
        webView.scrollView.refreshControl = refresh
        context.coordinator.refreshControl = refresh
        context.coordinator.attach(to: webView)
        state.attach(webView)

        var request = URLRequest(
            url: state.homeURL,
            cachePolicy: .useProtocolCachePolicy,
            timeoutInterval: 35
        )
        request.setValue("https://dexter.pw/", forHTTPHeaderField: "Referer")
        webView.load(request)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if state.webView !== webView {
            state.attach(webView)
        }
    }

    private static let polishScript = """
    (() => {
      try {
        document.documentElement.style.backgroundColor = '#050507';
        if (document.body) document.body.style.backgroundColor = '#050507';

        let viewport = document.querySelector('meta[name="viewport"]');
        if (viewport && !viewport.content.includes('viewport-fit')) {
          viewport.content += ', viewport-fit=cover';
        }

        if (!document.getElementById('dexter-ios-polish')) {
          const style = document.createElement('style');
          style.id = 'dexter-ios-polish';
          style.textContent = `
            html, body { background: #050507 !important; }
            * { -webkit-tap-highlight-color: transparent; }
            video { max-width: 100%; }
            ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
          `;
          (document.head || document.documentElement).appendChild(style);
        }

        document.querySelectorAll('video').forEach((video) => {
          video.setAttribute('playsinline', '');
          video.setAttribute('webkit-playsinline', '');
        });
      } catch (_) {}
    })();
    """

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        private let state: BrowserState
        private weak var webView: WKWebView?
        fileprivate weak var refreshControl: UIRefreshControl?
        private var progressObservation: NSKeyValueObservation?
        private var backObservation: NSKeyValueObservation?
        private var forwardObservation: NSKeyValueObservation?

        init(state: BrowserState) {
            self.state = state
        }

        func attach(to webView: WKWebView) {
            self.webView = webView

            progressObservation = webView.observe(\.estimatedProgress, options: [.new]) { [weak self] view, _ in
                DispatchQueue.main.async {
                    self?.state.progress = max(0, min(1, view.estimatedProgress))
                }
            }

            backObservation = webView.observe(\.canGoBack, options: [.new]) { [weak self] view, _ in
                DispatchQueue.main.async {
                    self?.state.canGoBack = view.canGoBack
                }
            }

            forwardObservation = webView.observe(\.canGoForward, options: [.new]) { [weak self] view, _ in
                DispatchQueue.main.async {
                    self?.state.canGoForward = view.canGoForward
                }
            }
        }

        @objc func refresh(_ sender: UIRefreshControl) {
            if let webView, webView.url != nil {
                webView.reload()
            } else {
                state.loadHome()
            }
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            state.beginLoading()
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            refreshControl?.endRefreshing()
            state.finishLoading(title: webView.title)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            handleFailure(error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            handleFailure(error)
        }

        private func handleFailure(_ error: Error) {
            refreshControl?.endRefreshing()
            let nsError = error as NSError
            guard nsError.code != NSURLErrorCancelled else { return }

            let message: String
            if nsError.code == NSURLErrorNotConnectedToInternet {
                message = "No internet connection."
            } else if nsError.code == NSURLErrorTimedOut {
                message = "Dexter took too long to respond."
            } else {
                message = "Dexter couldn't load this page."
            }
            state.failLoading(message)
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }

            let scheme = url.scheme?.lowercased() ?? ""
            let internalSchemes = ["http", "https", "about", "blob", "data"]

            if navigationAction.targetFrame == nil && internalSchemes.contains(scheme) {
                webView.load(navigationAction.request)
                decisionHandler(.cancel)
                return
            }

            if internalSchemes.contains(scheme) {
                decisionHandler(.allow)
                return
            }

            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
            decisionHandler(.cancel)
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            if let requestURL = navigationAction.request.url {
                webView.load(URLRequest(url: requestURL))
            }
            return nil
        }

        func webView(
            _ webView: WKWebView,
            runJavaScriptAlertPanelWithMessage message: String,
            initiatedByFrame frame: WKFrameInfo,
            completionHandler: @escaping () -> Void
        ) {
            guard let presenter = topViewController() else {
                completionHandler()
                return
            }

            let alert = UIAlertController(title: "Dexter", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            presenter.present(alert, animated: true)
        }

        func webView(
            _ webView: WKWebView,
            runJavaScriptConfirmPanelWithMessage message: String,
            initiatedByFrame frame: WKFrameInfo,
            completionHandler: @escaping (Bool) -> Void
        ) {
            guard let presenter = topViewController() else {
                completionHandler(false)
                return
            }

            let alert = UIAlertController(title: "Dexter", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
            alert.addAction(UIAlertAction(title: "Continue", style: .default) { _ in completionHandler(true) })
            presenter.present(alert, animated: true)
        }

        func webView(
            _ webView: WKWebView,
            runJavaScriptTextInputPanelWithPrompt prompt: String,
            defaultText: String?,
            initiatedByFrame frame: WKFrameInfo,
            completionHandler: @escaping (String?) -> Void
        ) {
            guard let presenter = topViewController() else {
                completionHandler(defaultText)
                return
            }

            let alert = UIAlertController(title: "Dexter", message: prompt, preferredStyle: .alert)
            alert.addTextField { field in field.text = defaultText }
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(nil) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                completionHandler(alert.textFields?.first?.text)
            })
            presenter.present(alert, animated: true)
        }

        private func topViewController() -> UIViewController? {
            let scenes = UIApplication.shared.connectedScenes
                .compactMap { $0 as? UIWindowScene }
                .filter { $0.activationState == .foregroundActive }

            guard let root = scenes
                .flatMap({ $0.windows })
                .first(where: { $0.isKeyWindow })?
                .rootViewController else {
                return nil
            }

            var current = root
            while let presented = current.presentedViewController {
                current = presented
            }
            return current
        }
    }
}
