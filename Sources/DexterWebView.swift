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
        configuration.applicationNameForUserAgent = "Dexter-iOS/1.1"

        let userContentController = WKUserContentController()
        userContentController.add(context.coordinator, name: "dexterBridge")
        userContentController.addUserScript(
            WKUserScript(
                source: Self.polishScript,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: false
            )
        )
        userContentController.addUserScript(
            WKUserScript(
                source: Self.playerEnhancementScript,
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
        webView.scrollView.bounces = false
        webView.scrollView.alwaysBounceVertical = false
        webView.scrollView.showsVerticalScrollIndicator = false
        webView.scrollView.showsHorizontalScrollIndicator = false

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
        const installPolish = () => {
          document.documentElement.style.backgroundColor = '#050507';
          if (document.body) document.body.style.backgroundColor = '#050507';

          let viewport = document.querySelector('meta[name="viewport"]');
          if (!viewport) {
            viewport = document.createElement('meta');
            viewport.name = 'viewport';
            viewport.content = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover';
            (document.head || document.documentElement).appendChild(viewport);
          } else {
            const parts = viewport.content.split(',').map(v => v.trim()).filter(Boolean);
            const required = ['viewport-fit=cover', 'maximum-scale=1', 'user-scalable=no'];
            required.forEach(value => {
              const key = value.split('=')[0];
              if (!parts.some(part => part.startsWith(key + '='))) parts.push(value);
            });
            viewport.content = parts.join(', ');
          }

          if (!document.getElementById('dexter-ios-native-polish')) {
            const style = document.createElement('style');
            style.id = 'dexter-ios-native-polish';
            style.textContent = `
              html, body {
                background: #050507 !important;
                overscroll-behavior: none !important;
                -webkit-text-size-adjust: 100% !important;
              }
              * {
                -webkit-tap-highlight-color: transparent !important;
              }
              body *:not(input):not(textarea):not(select):not([contenteditable="true"]) {
                -webkit-user-select: none !important;
                user-select: none !important;
                -webkit-touch-callout: none !important;
              }
              img, svg, video {
                -webkit-user-drag: none !important;
              }
              video {
                max-width: 100%;
              }
              video::cue {
                color: white !important;
                background: rgba(0,0,0,.68) !important;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
                text-shadow: 0 1px 4px rgba(0,0,0,.95) !important;
              }
              ::-webkit-scrollbar {
                width: 0 !important;
                height: 0 !important;
              }
            `;
            (document.head || document.documentElement).appendChild(style);
          }
        };

        installPolish();
        document.addEventListener('DOMContentLoaded', installPolish, { once: true });

        const isEditable = target => !!target?.closest?.('input, textarea, select, [contenteditable="true"]');
        document.addEventListener('contextmenu', event => {
          if (!isEditable(event.target)) event.preventDefault();
        }, true);
        document.addEventListener('selectstart', event => {
          if (!isEditable(event.target)) event.preventDefault();
        }, true);
        document.addEventListener('dragstart', event => {
          if (!isEditable(event.target)) event.preventDefault();
        }, true);
      } catch (_) {}
    })();
    """

    private static let playerEnhancementScript = """
    (() => {
      if (window.__dexterIOSInstalled) {
        window.__dexterEnhance?.();
        return;
      }
      window.__dexterIOSInstalled = true;

      const bridge = payload => {
        try {
          window.webkit?.messageHandlers?.dexterBridge?.postMessage(payload);
        } catch (_) {}
      };

      const iconRotate = `
        <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 7V3l-4 4 4 4V7a8 8 0 1 1-2.34-5.66"/>
          <rect x="7.2" y="8" width="9.6" height="8" rx="1.7" transform="rotate(90 12 12)"/>
        </svg>`;

      const iconDownload = `
        <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3v11"/><path d="m8 10 4 4 4-4"/><path d="M5 19h14"/>
        </svg>`;

      const visible = element => {
        if (!element) return false;
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 1 && rect.height > 1 && style.display !== 'none' && style.visibility !== 'hidden';
      };

      const meta = button => [
        button.getAttribute('aria-label'),
        button.getAttribute('title'),
        button.getAttribute('data-tooltip'),
        button.getAttribute('data-testid'),
        button.className,
        button.textContent
      ].filter(Boolean).join(' ').toLowerCase();

      const makeButton = (reference, id, label, icon) => {
        const button = document.createElement('button');
        button.id = id;
        button.type = 'button';
        button.setAttribute('aria-label', label);
        button.setAttribute('title', label);
        if (reference?.className && typeof reference.className === 'string') {
          button.className = reference.className;
        } else {
          button.className = 'dexter-ios-fallback-control';
        }
        button.innerHTML = icon;
        button.style.color = 'white';
        button.style.webkitTapHighlightColor = 'transparent';
        return button;
      };

      const ensureControlStyle = () => {
        if (document.getElementById('dexter-ios-control-style')) return;
        const style = document.createElement('style');
        style.id = 'dexter-ios-control-style';
        style.textContent = `
          .dexter-ios-fallback-control {
            position: fixed !important;
            z-index: 2147483646 !important;
            width: 42px !important;
            height: 42px !important;
            display: grid !important;
            place-items: center !important;
            border: 1px solid rgba(255,255,255,.16) !important;
            border-radius: 50% !important;
            color: white !important;
            background: rgba(12,12,16,.72) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            backdrop-filter: blur(18px) !important;
            box-shadow: 0 8px 30px rgba(0,0,0,.28) !important;
          }
          #dexter-ios-download.dexter-ios-fallback-control {
            top: calc(env(safe-area-inset-top) + 58px) !important;
            right: 16px !important;
          }
          #dexter-ios-rotate.dexter-ios-fallback-control {
            right: 18px !important;
            bottom: calc(env(safe-area-inset-bottom) + 62px) !important;
          }
          #dexter-ios-download svg, #dexter-ios-rotate svg {
            pointer-events: none !important;
          }
        `;
        (document.head || document.documentElement).appendChild(style);
      };

      const sendMediaInfo = video => {
        if (!video) return;
        const trackElements = Array.from(video.querySelectorAll('track'));
        const direct = Array.from(document.querySelectorAll('a[href]'))
          .map(anchor => anchor.href)
          .find(href => /\.(mp4|m4v|mov|mkv|webm)(?:\?|#|$)/i.test(href || '')) || null;

        bridge({
          type: 'media',
          src: video.currentSrc || video.src || null,
          directDownload: direct,
          subtitleCount: Math.max(trackElements.length, video.textTracks?.length || 0)
        });
      };

      const preserveCaptionsForPiP = video => {
        if (!video || video.dataset.dexterCaptionBridge === '1') return;
        video.dataset.dexterCaptionBridge = '1';
        video.setAttribute('playsinline', '');
        video.setAttribute('webkit-playsinline', '');
        try { video.disablePictureInPicture = false; } catch (_) {}

        const rememberCaption = () => {
          const tracks = video.textTracks;
          if (!tracks) return;
          for (let index = 0; index < tracks.length; index++) {
            if (tracks[index].mode === 'showing' || tracks[index].mode === 'hidden') {
              video.dataset.dexterCaptionIndex = String(index);
              if (tracks[index].language) video.dataset.dexterCaptionLanguage = tracks[index].language;
            }
          }
          sendMediaInfo(video);
        };

        try { video.textTracks?.addEventListener?.('change', rememberCaption); } catch (_) {}
        ['loadedmetadata', 'durationchange', 'play'].forEach(name => {
          video.addEventListener(name, () => sendMediaInfo(video), { passive: true });
        });

        video.addEventListener('webkitpresentationmodechanged', () => {
          try {
            if (video.webkitPresentationMode !== 'picture-in-picture') return;
            const tracks = video.textTracks;
            if (!tracks || !tracks.length) return;

            let index = Number.parseInt(video.dataset.dexterCaptionIndex || '-1', 10);
            if (!(index >= 0 && index < tracks.length)) {
              index = Array.from(tracks).findIndex(track => track.mode === 'showing');
            }
            if (index < 0) {
              index = Array.from(tracks).findIndex(track => track.mode === 'hidden');
            }
            if (index < 0) {
              index = Array.from(tracks).findIndex(track => /^(ar|ara|arabic)/i.test(track.language || track.label || ''));
            }
            if (index < 0 && tracks.length === 1) index = 0;

            if (index >= 0 && index < tracks.length) {
              tracks[index].mode = 'showing';
            }
          } catch (_) {}
        }, { passive: true });

        rememberCaption();
      };

      const installPlayerButtons = () => {
        ensureControlStyle();
        const onWatchPage = location.pathname === '/watch' || location.pathname.startsWith('/watch/');
        if (!onWatchPage) {
          document.getElementById('dexter-ios-rotate')?.remove();
          document.getElementById('dexter-ios-download')?.remove();
          return;
        }

        const buttons = Array.from(document.querySelectorAll('button')).filter(visible);

        if (!document.getElementById('dexter-ios-rotate')) {
          const fullscreen = buttons.find(button => /full\s*screen|fullscreen|expand/.test(meta(button)));
          const rotate = makeButton(fullscreen, 'dexter-ios-rotate', 'Rotate screen', iconRotate);
          rotate.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            bridge({ type: 'rotate' });
          }, true);

          if (fullscreen?.parentElement) {
            fullscreen.parentElement.insertBefore(rotate, fullscreen);
          } else {
            rotate.className = 'dexter-ios-fallback-control';
            document.body?.appendChild(rotate);
          }
        }

        if (!document.getElementById('dexter-ios-download')) {
          const topButtons = buttons.filter(button => button.getBoundingClientRect().top < 190);
          let row = null;
          for (const button of topButtons) {
            const parent = button.parentElement;
            if (!parent) continue;
            const count = Array.from(parent.querySelectorAll(':scope > button')).filter(visible).length;
            if (count >= 3) { row = parent; break; }
          }

          const reference = row ? Array.from(row.querySelectorAll(':scope > button')).filter(visible).at(-1) : null;
          const download = makeButton(reference, 'dexter-ios-download', 'Download', iconDownload);
          download.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            const video = Array.from(document.querySelectorAll('video')).find(visible) || document.querySelector('video');
            if (video) sendMediaInfo(video);
            bridge({ type: 'download' });
          }, true);

          if (row) {
            row.appendChild(download);
          } else {
            download.className = 'dexter-ios-fallback-control';
            document.body?.appendChild(download);
          }
        }
      };

      const postPage = () => bridge({ type: 'page', url: location.href, title: document.title || 'Dexter' });

      window.__dexterEnhance = () => {
        postPage();
        document.querySelectorAll('video').forEach(video => preserveCaptionsForPiP(video));
        installPlayerButtons();
      };

      const schedule = () => requestAnimationFrame(() => window.__dexterEnhance?.());
      const observer = new MutationObserver(schedule);
      observer.observe(document.documentElement, { childList: true, subtree: true });

      ['pushState', 'replaceState'].forEach(method => {
        const original = history[method];
        if (typeof original !== 'function') return;
        history[method] = function(...args) {
          const result = original.apply(this, args);
          setTimeout(schedule, 0);
          return result;
        };
      });
      addEventListener('popstate', schedule, { passive: true });
      addEventListener('hashchange', schedule, { passive: true });
      addEventListener('load', schedule, { once: true });
      schedule();
    })();
    """

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        private let state: BrowserState
        private weak var webView: WKWebView?
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

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "dexterBridge", let body = message.body as? [String: Any], let type = body["type"] as? String else {
                return
            }

            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                switch type {
                case "page":
                    let url = (body["url"] as? String).flatMap(URL.init(string:))
                    self.state.updatePage(url: url, title: body["title"] as? String)
                case "media":
                    let count = (body["subtitleCount"] as? NSNumber)?.intValue ?? 0
                    self.state.updateMedia(
                        src: body["src"] as? String,
                        directDownload: body["directDownload"] as? String,
                        subtitleCount: count
                    )
                case "rotate":
                    self.state.rotatePlayer()
                case "download":
                    self.state.downloadCurrentMedia()
                default:
                    break
                }
            }
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            state.beginLoading(url: webView.url)
        }

        func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
            state.updatePage(url: webView.url, title: webView.title)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            state.finishLoading(url: webView.url, title: webView.title)
            webView.evaluateJavaScript("window.__dexterEnhance && window.__dexterEnhance();", completionHandler: nil)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            handleFailure(error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            handleFailure(error)
        }

        private func handleFailure(_ error: Error) {
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
