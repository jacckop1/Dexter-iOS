import SwiftUI
import AVFoundation

@main
struct DexterApp: App {
    init() {
        configureMediaSession()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .preferredColorScheme(.dark)
        }
    }

    private func configureMediaSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(
                .playback,
                mode: .moviePlayback,
                options: [.allowAirPlay]
            )
        } catch {
            // WebKit still manages media playback if the audio session cannot be preconfigured.
        }
    }
}
