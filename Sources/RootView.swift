import SwiftUI

struct RootView: View {
    @StateObject private var browser = BrowserState()
    @StateObject private var network = NetworkMonitor()

    private var initialFailure: String? {
        if !network.isConnected {
            return "Check your connection and try again."
        }
        return browser.errorMessage
    }

    var body: some View {
        ZStack {
            Color(red: 0.018, green: 0.018, blue: 0.025)
                .ignoresSafeArea()

            DexterWebView(state: browser)
                .opacity(browser.hasLoadedOnce ? 1 : 0.02)

            if !browser.hasLoadedOnce, let message = initialFailure {
                ConnectionErrorView(
                    title: network.isConnected ? "Unable to Load Dexter" : "You're Offline",
                    message: message,
                    retry: browser.reload
                )
                .transition(.opacity)
            } else if !browser.hasLoadedOnce {
                LaunchView()
                    .transition(.opacity)
            }
        }
        .overlay(alignment: .top) {
            VStack(spacing: 8) {
                if browser.isLoading && browser.progress > 0.01 && browser.progress < 0.99 {
                    GeometryReader { proxy in
                        Capsule()
                            .fill(
                                LinearGradient(
                                    colors: [
                                        Color(red: 0.42, green: 0.20, blue: 0.92),
                                        Color(red: 0.08, green: 0.62, blue: 0.84)
                                    ],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: proxy.size.width * browser.progress, height: 2)
                            .animation(.easeOut(duration: 0.18), value: browser.progress)
                    }
                    .frame(height: 2)
                }

                if browser.hasLoadedOnce && !network.isConnected {
                    StatusPill(icon: "wifi.slash", text: "Offline")
                        .transition(.move(edge: .top).combined(with: .opacity))
                } else if browser.hasLoadedOnce, browser.errorMessage != nil {
                    StatusPill(icon: "arrow.clockwise", text: "Tap to retry", action: browser.reload)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .padding(.horizontal, 12)
            .padding(.top, 4)
        }
        .animation(.easeInOut(duration: 0.24), value: network.isConnected)
        .animation(.easeInOut(duration: 0.24), value: browser.hasLoadedOnce)
        .onChange(of: network.isConnected) { connected in
            if connected && !browser.hasLoadedOnce && browser.errorMessage != nil {
                browser.reload()
            }
        }
    }
}
