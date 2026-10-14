import AVFoundation
import Foundation
import Speech

/// One-shot on-device dictation for the terminal. The local page uses the browser microphone instead.
final class Listener {
    private let engine = AVAudioEngine()
    private let lock = NSLock()
    private var task: SFSpeechRecognitionTask?
    private var latest = ""
    private var finished = false

    func start() {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                guard status == .authorized else {
                    fputs(
                        "Speech recognition is not allowed for this terminal. Enable Speech Recognition for Terminal in System Settings, or run python3 scripts/athena_ui.py and press Listen.\n",
                        stderr
                    )
                    exit(1)
                }
                self.recognize()
            }
        }
        dispatchMain()
    }

    private func recognize() {
        guard let recognizer = SFSpeechRecognizer(), recognizer.isAvailable else {
            fputs("Speech recognition is not available. Use Listen on the ATHENA page.\n", stderr)
            exit(1)
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else {
            fputs("No microphone is available.\n", stderr)
            exit(1)
        }

        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            request.append(buffer)
        }
        engine.prepare()
        do {
            try engine.start()
        } catch {
            fputs("Could not start the microphone. \(error.localizedDescription)\n", stderr)
            exit(1)
        }

        task = recognizer.recognitionTask(with: request) { result, error in
            if let result {
                self.lock.lock()
                self.latest = result.bestTranscription.formattedString
                self.lock.unlock()
                if result.isFinal {
                    self.finish()
                }
            }
            if error != nil {
                self.finish()
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 12) {
            self.finish()
        }
    }

    private func finish() {
        lock.lock()
        if finished {
            lock.unlock()
            return
        }
        finished = true
        let spoken = latest.trimmingCharacters(in: .whitespacesAndNewlines)
        lock.unlock()

        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        task?.cancel()

        guard !spoken.isEmpty else {
            fputs("No speech recognized. Speak, then pause.\n", stderr)
            exit(2)
        }
        print(spoken)
        fflush(stdout)
        exit(0)
    }
}

Listener().start()
