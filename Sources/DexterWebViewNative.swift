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

        let controller = WKUserContentController()
        controller.add(context.coordinator, name: "dexterBridge")
        controller.addUserScript(
            WKUserScript(source: Self.nativePolishScript, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        )
        controller.addUserScript(
            WKUserScript(source: Self.playerBridgeScript, injectionTime: .atDocumentEnd, forMainFrameOnly: false)
        )
        configuration.userContentController = controller

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

        var request = URLRequest(url: state.homeURL, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 35)
        request.setValue("https://dexter.pw/", forHTTPHeaderField: "Referer")
        webView.load(request)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if state.webView !== webView {
            state.attach(webView)
        }
    }

    private static let nativePolishScript = #"""
    (() => {
      const install = () => {
        try {
          document.documentElement.style.backgroundColor = '#050507';
          if (document.body) document.body.style.backgroundColor = '#050507';

          let viewport = document.querySelector('meta[name="viewport"]');
          if (!viewport) {
            viewport = document.createElement('meta');
            viewport.name = 'viewport';
            viewport.content = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover';
            (document.head || document.documentElement).appendChild(viewport);
          } else {
            const current = viewport.content || '';
            if (!current.includes('viewport-fit')) viewport.content = current + ', viewport-fit=cover';
            if (!current.includes('maximum-scale')) viewport.content += ', maximum-scale=1';
            if (!current.includes('user-scalable')) viewport.content += ', user-scalable=no';
          }

          if (!document.getElementById('dexter-native-polish')) {
            const style = document.createElement('style');
            style.id = 'dexter-native-polish';
            style.textContent = `
              html, body {
                background: #050507 !important;
                overscroll-behavior: none !important;
                -webkit-text-size-adjust: 100% !important;
              }
              * { -webkit-tap-highlight-color: transparent !important; }
              body *:not(input):not(textarea):not(select):not([contenteditable="true"]) {
                -webkit-user-select: none !important;
                user-select: none !important;
                -webkit-touch-callout: none !important;
              }
              img, svg, video { -webkit-user-drag: none !important; }
              video { max-width: 100% !important; }
              video::cue {
                color: #fff !important;
                background: rgba(0,0,0,.70) !important;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
                text-shadow: 0 1px 4px rgba(0,0,0,.95) !important;
              }
              ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
            `;
            (document.head || document.documentElement).appendChild(style);
          }
        } catch (_) {}
      };

      install();
      document.addEventListener('DOMContentLoaded', install, { once: true });

      const editable = target => !!target?.closest?.('input, textarea, select, [contenteditable="true"]');
      document.addEventListener('contextmenu', event => { if (!editable(event.target)) event.preventDefault(); }, true);
      document.addEventListener('selectstart', event => { if (!editable(event.target)) event.preventDefault(); }, true);
      document.addEventListener('dragstart', event => { if (!editable(event.target)) event.preventDefault(); }, true);
    })();
    """#

    private static let playerBridgeScript = #"""
    (() => {
      if (window.__dexterNativeInstalled) {
        window.__dexterNativeEnhance?.();
        return;
      }
      window.__dexterNativeInstalled = true;

      const post = payload => {
        try { window.webkit?.messageHandlers?.dexterBridge?.postMessage(payload); } catch (_) {}
      };

      const visible = element => {
        if (!element) return false;
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 2 && rect.height > 2 && style.display !== 'none' && style.visibility !== 'hidden';
      };

      const buttonMeta = button => [
        button.getAttribute('aria-label'),
        button.getAttribute('title'),
        button.getAttribute('data-tooltip'),
        button.getAttribute('data-testid'),
        typeof button.className === 'string' ? button.className : '',
        button.textContent
      ].filter(Boolean).join(' ').toLowerCase();

      const ensureControlCSS = () => {
        if (document.getElementById('dexter-native-controls-css')) return;
        const style = document.createElement('style');
        style.id = 'dexter-native-controls-css';
        style.textContent = `
          .dexter-native-fallback {
            position: fixed !important;
            z-index: 2147483646 !important;
            width: 42px !important;
            height: 42px !important;
            display: grid !important;
            place-items: center !important;
            border: 1px solid rgba(255,255,255,.15) !important;
            border-radius: 999px !important;
            color: #fff !important;
            background: rgba(12,12,16,.74) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            backdrop-filter: blur(18px) !important;
            box-shadow: 0 8px 30px rgba(0,0,0,.28) !important;
          }
          #dexter-native-download.dexter-native-fallback {
            top: calc(env(safe-area-inset-top) + 58px) !important;
            right: 16px !important;
          }
          #dexter-native-rotate.dexter-native-fallback {
            right: 18px !important;
            bottom: calc(env(safe-area-inset-bottom) + 62px) !important;
          }
          #dexter-native-download svg, #dexter-native-rotate svg { pointer-events: none !important; }
        `;
        (document.head || document.documentElement).appendChild(style);
      };

      const rotateIcon = `
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M20 7V3l-4 4 4 4V7a8 8 0 1 1-2.34-5.66"/>
          <rect x="7.2" y="8" width="9.6" height="8" rx="1.7" transform="rotate(90 12 12)"/>
        </svg>`;

      const downloadIcon = `
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3v11"/><path d="m8 10 4 4 4-4"/><path d="M5 19h14"/>
        </svg>`;

      const makeButton = (reference, id, title, icon) => {
        const button = document.createElement('button');
        button.id = id;
        button.type = 'button';
        button.setAttribute('aria-label', title);
        button.setAttribute('title', title);
        button.className = reference && typeof reference.className === 'string' && reference.className
          ? reference.className
          : 'dexter-native-fallback';
        button.innerHTML = icon;
        button.style.color = '#fff';
        button.style.webkitTapHighlightColor = 'transparent';
        return button;
      };

      const directMediaLink = () => {
        const extensions = ['.mp4', '.m4v', '.mov', '.mkv', '.webm'];
        const links = Array.from(document.querySelectorAll('a[href]'));
        for (const anchor of links) {
          try {
            const url = new URL(anchor.href, location.href);
            const path = url.pathname.toLowerCase();
            if (extensions.some(extension => path.endsWith(extension))) return url.href;
          } catch (_) {}
        }
        return null;
      };

      const sendMedia = video => {
        if (!video) return;
        post({
          type: 'media',
          src: video.currentSrc || video.src || null,
          directDownload: directMediaLink(),
          subtitleCount: Math.max(video.querySelectorAll('track').length, video.textTracks?.length || 0)
        });
      };

      const prepareCaptions = video => {
        if (!video || video.dataset.dexterNativeCaptions === '1') return;
        video.dataset.dexterNativeCaptions = '1';
        video.setAttribute('playsinline', '');
        video.setAttribute('webkit-playsinline', '');
        try { video.disablePictureInPicture = false; } catch (_) {}

        const remember = () => {
          const tracks = video.textTracks;
          if (!tracks) return;
          for (let index = 0; index < tracks.length; index++) {
            if (tracks[index].mode === 'showing' || tracks[index].mode === 'hidden') {
              video.dataset.dexterCaptionIndex = String(index);
            }
          }
          sendMedia(video);
        };

        try { video.textTracks?.addEventListener?.('change', remember); } catch (_) {}
        ['loadedmetadata', 'durationchange', 'play'].forEach(eventName => {
          video.addEventListener(eventName, () => sendMedia(video), { passive: true });
        });

        video.addEventListener('webkitpresentationmodechanged', () => {
          try {
            if (video.webkitPresentationMode !== 'picture-in-picture') return;
            const tracks = video.textTracks;
            if (!tracks || tracks.length === 0) return;

            let selected = Number.parseInt(video.dataset.dexterCaptionIndex || '-1', 10);
            if (!(selected >= 0 && selected < tracks.length)) {
              selected = Array.from(tracks).findIndex(track => track.mode === 'showing');
            }
            if (selected < 0) {
              selected = Array.from(tracks).findIndex(track => track.mode === 'hidden');
            }
            if (selected < 0) {
              selected = Array.from(tracks).findIndex(track => {
                const value = ((track.language || '') + ' ' + (track.label || '')).toLowerCase();
                return value === 'ar' || value.startsWith('ar ') || value.includes('arabic') || value.includes('العربية');
              });
            }
            if (selected < 0 && tracks.length === 1) selected = 0;
            if (selected >= 0 && selected < tracks.length) tracks[selected].mode = 'showing';
          } catch (_) {}
        }, { passive: true });

        remember();
      };

      const installPlayerControls = () => {
        ensureControlCSS();
        const watch = location.pathname === '/watch' || location.pathname.startsWith('/watch/');
        if (!watch) {
          document.getElementById('dexter-native-rotate')?.remove();
          document.getElementById('dexter-native-download')?.remove();
          return;
        }

        const buttons = Array.from(document.querySelectorAll('button')).filter(visible);

        if (!document.getElementById('dexter-native-rotate')) {
          const fullscreen = buttons.find(button => {
            const value = buttonMeta(button);
            return value.includes('fullscreen') || value.includes('full screen') || value.includes('expand');
          });
          const rotate = makeButton(fullscreen, 'dexter-native-rotate', 'Rotate screen', rotateIcon);
          rotate.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            post({ type: 'rotate' });
          }, true);

          if (fullscreen?.parentElement) {
            fullscreen.parentElement.insertBefore(rotate, fullscreen);
          } else {
            rotate.className = 'dexter-native-fallback';
            document.body?.appendChild(rotate);
          }
        }

        if (!document.getElementById('dexter-native-download')) {
          const topButtons = buttons.filter(button => button.getBoundingClientRect().top < 190);
          let row = null;
          for (const button of topButtons) {
            const parent = button.parentElement;
            if (!parent) continue;
            const children = Array.from(parent.children).filter(child => child.tagName === 'BUTTON' && visible(child));
            if (children.length >= 3) { row = parent; break; }
          }

          let reference = null;
          if (row) {
            const children = Array.from(row.children).filter(child => child.tagName === 'BUTTON' && visible(child));
            reference = children.length ? children[children.length - 1] : null;
          }

          const download = makeButton(reference, 'dexter-native-download', 'Download', downloadIcon);
          download.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            const videos = Array.from(document.querySelectorAll('video'));
            const video = videos.find(visible) || videos[0];
            if (video) sendMedia(video);
            post({ type: 'download' });
          }, true);

          if (row) {
            row.appendChild(download);
          } else {
            download.className = 'dexter-native-fallback';
            document.body?.appendChild(download);
          }
        }
      };

      let scheduled = false;
      const enhance = () => {
        scheduled = false;
        post({ type: 'page', url: location.href, title: document.title || 'Dexter' });
        document.querySelectorAll('video').forEach(prepareCaptions);
        installPlayerControls();
      };
      const schedule = () => {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(enhance);
      };

      window.__dexterNativeEnhance = schedule;
      new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });

      ['pushState', 'replaceState'].forEach(name => {
        const original = history[name];
        if (typeof original !== 'function') return;
        history[name] = function(...args) {
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
    """#

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
                DispatchQueue.main.async { self?.state.canGoBack = view.canGoBack }
            }
            forwardObservation = webView.observe(\.canGoForward, options: [.new]) { [weak self] view, _ in
                DispatchQueue.main.async { self?.state.canGoForward = view.canGoForward }
            }
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "dexterBridge",
                  let body = message.body as? [String: Any],
                  let type = body["type"] as? String else { return }

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
            webView.evaluateJavaScript("window.__dexterNativeEnhance && window.__dexterNativeEnhance();", completionHandler: nil)
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
            if nsError.code == NSURLErrorNotConnectedToInternet {
                state.failLoading("No internet connection.")
            } else if nsError.code == NSURLErrorTimedOut {
                state.failLoading("Dexter took too long to respond.")
            } else {
                state.failLoading("Dexter couldn't load this page.")
            }
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
            if let url = navigationAction.request.url {
                webView.load(URLRequest(url: url))
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

        private func topViewController() -> UIViewController? {
            guard let root = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .filter({ $0.activationState == .foregroundActive })
                .flatMap({ $0.windows })
                .first(where: { $0.isKeyWindow })?
                .rootViewController else { return nil }

            var current = root
            while let presented = current.presentedViewController {
                current = presented
            }
            return current
        }
    }
}
