import SwiftUI
import UIKit

struct DexterMark: View {
    let size: CGFloat

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.27, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.17, green: 0.11, blue: 0.38),
                            Color(red: 0.42, green: 0.20, blue: 0.88),
                            Color(red: 0.08, green: 0.60, blue: 0.84)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

            RoundedRectangle(cornerRadius: size * 0.27, style: .continuous)
                .stroke(Color.white.opacity(0.18), lineWidth: 1)

            Text("D")
                .font(.system(size: size * 0.56, weight: .black, design: .rounded))
                .foregroundStyle(.white)
                .offset(x: -size * 0.015, y: -size * 0.025)
        }
        .frame(width: size, height: size)
        .shadow(color: Color(red: 0.42, green: 0.20, blue: 0.95).opacity(0.40), radius: size * 0.22)
    }
}

struct LaunchView: View {
    @State private var animate = false

    var body: some View {
        ZStack {
            Color(red: 0.018, green: 0.018, blue: 0.025)
                .ignoresSafeArea()

            RadialGradient(
                colors: [
                    Color(red: 0.33, green: 0.12, blue: 0.70).opacity(animate ? 0.28 : 0.12),
                    Color.clear
                ],
                center: animate ? .topTrailing : .bottomLeading,
                startRadius: 24,
                endRadius: 420
            )
            .ignoresSafeArea()
            .animation(.easeInOut(duration: 3.2).repeatForever(autoreverses: true), value: animate)

            VStack(spacing: 20) {
                ZStack {
                    Circle()
                        .trim(from: 0.08, to: 0.74)
                        .stroke(
                            AngularGradient(
                                colors: [.clear, .white.opacity(0.08), .white.opacity(0.70), .clear],
                                center: .center
                            ),
                            style: StrokeStyle(lineWidth: 1.4, lineCap: .round)
                        )
                        .frame(width: 118, height: 118)
                        .rotationEffect(.degrees(animate ? 360 : 0))
                        .animation(.linear(duration: 4.2).repeatForever(autoreverses: false), value: animate)

                    DexterMark(size: 86)
                        .scaleEffect(animate ? 1.025 : 0.985)
                        .animation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true), value: animate)
                }

                VStack(spacing: 7) {
                    Text("DEXTER")
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .tracking(6)
                        .foregroundStyle(.white)

                    Text("CINEMA ON iOS")
                        .font(.system(size: 10, weight: .semibold, design: .rounded))
                        .tracking(3)
                        .foregroundStyle(.white.opacity(0.42))
                }

                ProgressView()
                    .tint(.white.opacity(0.72))
                    .scaleEffect(0.82)
                    .padding(.top, 8)
            }
        }
        .onAppear { animate = true }
    }
}

struct ConnectionErrorView: View {
    let title: String
    let message: String
    let retry: () -> Void

    var body: some View {
        ZStack {
            Color(red: 0.018, green: 0.018, blue: 0.025)
                .ignoresSafeArea()

            VStack(spacing: 18) {
                DexterMark(size: 68)
                    .padding(.bottom, 8)

                Image(systemName: "wifi.exclamationmark")
                    .font(.system(size: 28, weight: .medium))
                    .foregroundStyle(.white.opacity(0.82))

                Text(title)
                    .font(.system(size: 23, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)

                Text(message)
                    .font(.system(size: 14, weight: .medium, design: .rounded))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.white.opacity(0.54))
                    .padding(.horizontal, 34)

                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    retry()
                } label: {
                    Label("Try Again", systemImage: "arrow.clockwise")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 22)
                        .padding(.vertical, 12)
                        .background(
                            LinearGradient(
                                colors: [
                                    Color(red: 0.34, green: 0.18, blue: 0.80),
                                    Color(red: 0.10, green: 0.49, blue: 0.76)
                                ],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
                .padding(.top, 6)
            }
        }
    }
}

struct StatusPill: View {
    let icon: String
    let text: String
    var action: (() -> Void)? = nil

    var body: some View {
        Button {
            action?()
        } label: {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 12, weight: .semibold))
                Text(text)
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .lineLimit(1)
            }
            .foregroundStyle(.white.opacity(0.90))
            .padding(.horizontal, 13)
            .padding(.vertical, 8)
            .background(.ultraThinMaterial, in: Capsule())
            .overlay(Capsule().stroke(.white.opacity(0.10), lineWidth: 0.6))
        }
        .buttonStyle(.plain)
        .disabled(action == nil)
    }
}
