# AstroCare — astronaut-first offline demo

**[▶ Launch the AstroCare live demo](https://astrocare-crew-demo.onrender.com/)**

To run AstroCare locally, run `python server.py` and open http://127.0.0.1:8765.

## Share a live demo

1. Put these project files at the root of your GitHub repository, with
   `render.yaml`, `server.py`, and `index.html` next to each other.
2. In the [Render Dashboard](https://dashboard.render.com/), choose **New → Blueprint**,
   connect the GitHub repository and select the branch with the project files.
3. Review the free web service and choose **Deploy Blueprint**. Once the service
   is live, use its `onrender.com` URL as the project demo link.

GitHub stores the source code. Render runs the Python API that the interface
depends on. The hosted demo keeps reports, exercise records and journal entries
in a temporary database per browser session. Use fictional details only. Records
can disappear after a restart or redeploy, and the first visit after inactivity
may take a moment.

## Visible workflow
1. Simulated daily health measurements (six cards).
2. Button **I Have Other Symptoms** (or **No Other Symptoms**).
3. Interactive body region selector and original dataset topic groups.
4. One question at a time; Yes / No / Unknown or free text. Optional local speech synthesis reads questions aloud.
5. A single astronaut-facing **Personal Health Guidance** result card.

The pre-mission profile is **not displayed** in the astronaut UI. It is a future feature; the existing backend storage remains in the project for later development. No diseases or candidate patterns are displayed to the astronaut. The server stores case assessments for future clinician review.

## Important limits
- Demo-only: all six daily values are simulated; no hardware is connected.
- Clinical operation is disabled. The supplied source JSON contains narrative drafts without approved executable clinical rules. No actual diagnosis, treatment, medical test order, or medication recommendation is generated.
- No real emergency transmission. SOS prepares a local text report only.
- Questions preserve the supplied source wording, including some combined questions that need clinical review and splitting before clinical use.
- Speech synthesis may depend on installed voices. Offline voice recognition is not included.
- All records are stored locally in `local_demo.sqlite3` (demo-only; not production medical security).
- The underlying generic rule engine, synthetic test fixtures, original IDs and sources are retained unchanged.

Run tests: `python -m unittest discover -s tests -v` from the project directory.

## Easier symptom answers update
The original symptom questions, IDs and all assessment logic are unchanged. For 40 selected original questions, the interface now shows separate, one-tap answer choices and an optional notes box instead of requiring free text. All other questions retain their original controls. These choice lists are UI-only draft answer categories, not reviewed medical rules. Structured answers are stored under the original question ID as `fields` and `notes`; unanswered fields are left absent (unknown).

## Added: Create Report and local voice answers
- **Create Report** reveals a UTC date filter and locally saved assessment reports. Choose a date or All Dates. Reports contain case reference, symptom answers, voice transcripts (if any), and simulated daily readings. Only saved assessment cases appear; a no-other-symptoms check currently saves a follow-up entry, not a full case report.
- **Answer by Voice** requests the microphone and uses browser SpeechRecognition **only if the browser exposes `available()` and reports an already installed on-device `en-US` language pack**. It sets `processLocally=true`; there is no cloud fallback. Some browsers will not support this feature. Install an appropriate local language pack ahead of time on supported hardware/browser; no installation or network calls are initiated by the app.
- Spoken text is stored as a transcript alongside the answer. For yes/no, only unambiguous exact answers are mapped automatically. For multi-part choice questions, only exact option matches are selected; otherwise the transcript is retained for review, never guessed. Users should verify all recognized answers.
- Speech transcription is not clinically validated and may be inaccurate. The demo database is unencrypted; use synthetic information only.

## Added wellness features (without changing medical flow)
- **Daily Exercise Check:** Yes / No / Not yet, optional activity and minutes. Saves one record per UTC date to local SQLite. This is a self-report, not sensor verification or an exercise prescription.
- **Journaling tab:** Twelve built-in offline reflection prompts on love, life, hope, friendship, gratitude, Earth and more; private writing area and saved-entry history. No AI, diagnosis or mood inference. Entries are stored locally unencrypted in the demo database; do not enter sensitive real patient information.
- All prior Daily Scan, Body Map, questions, on-device voice pack controls, reports, results and conditional emergency interface remain in place.

## New small additions
- Journaling: after saving a reflection, a short original, encouraging quote appears. Mentions of family (including Arabic family words) trigger a family-themed quote. No AI, cloud, or psychological inference.
- Exercise: cardio and resistance entries are always visible; hours and minutes can be recorded for each. Partial progress can be saved, but completed status requires both exercise types and positive durations. Existing records and other application workflows are retained.
