# Apro - Bridge 🌉

![Status](https://img.shields.io/badge/status-stable-green) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) [![AnkiProTools](https://img.shields.io/badge/by-AnkiProTools-blueviolet)](https://AnkiProTools.com) ![Anki](https://img.shields.io/badge/Anki-2.1.49+-lightgray)

The **Apro - Bridge** add-on is a lightweight HTTP server that runs inside Anki, providing external applications (such as [CineCard](https://github.com/AnkiProTools1/CineCard) and Synapse) with a robust, controlled, and efficient way to manage your Anki notes and media.

It acts as the necessary communication layer for seamless, high-speed card creation and updating.

## ✨Features 

The **Apro - Bridge** add-on employs a local server architecture similar to the popular **AnkiConnect** add-on, but with a streamlined focus on high-speed card creation, patching, and media upload for companion applications.

Apro - Bridge extends the standard Anki interaction by offering granular control over notes:

* **Note Creation:** Quickly add new notes using the legacy AnkiConnect format.
* **Targeted Field Updates (PATCH):** Update specific field values of an existing note using its ID.
* **Note Deletion (DELETE):** Permanently remove notes by ID via API request.
* **Tag Management:** Supports adding tags, removing tags, and completely replacing the tags on existing notes.
* **Media Upload (PUT):** Upload base64-encoded media data directly into Anki's media folder, returning the final filename for use in fields.
* **Information Retrieval:** Query deck names, note types, and specific note/model details (fields, cloze status, templates, CSS).
* **Stability:** Runs on the main Anki task manager thread to ensure database integrity.

---

## 🚀Getting Started 

### Prerequisites

* **Anki Desktop** (version 2.1.49 or newer recommended).
* An external application (e.g., [CineCard](https://github.com/AnkiProTools1/CineCard)) that supports communication with Apro - Bridge on the specified host and port.

### Installation (The Easy Way)

The recommended way to install **Apro - Bridge** is by using the official Anki add-on package file:

1.  **Download** the latest `apro-bridge.ankiaddon` file from the [Releases page](https://github.com/AnkiProTools1/apro-bridge/releases).
2.  Ensure Anki is completely closed.
3.  **Double-click** the downloaded `apro-bridge.ankiaddon` file.
4.  Anki will open and prompt you to install the add-on. Confirm the installation.
5.  **Restart Anki** if prompted. The add-on server will start automatically when your profile loads.

---

## 🔌API & Connectivity 

The bridge starts automatically when your Anki profile is loaded and runs as a local server:

* **Host:** `localhost`
* **Port:** `8767`
* **Base URL:** `http://localhost:8767/`

For detailed request/response JSON formats, please refer to the source code.

| HTTP Method | Path/Action | Description |
| :--- | :--- | :--- |
| `POST` | `/` (with `action: notesInfo`) | Retrieve detailed info for notes by ID. |
| `PATCH` | `/` | Update specified fields on a note by ID. |
| `DELETE` | `/` | Delete a note by ID. |
| `PUT` | `/` | Upload media (base64) to the Anki media folder. |
| `GET` | `/model-fields?modelName=...` | Get model structure (fields, templates, cloze info). |
| `POST` | `action: updateNoteTags` | **Replace** all tags on a note. |
| `POST` | `action: addTags` | **Add** a set of tags to notes. |
| `POST` | `action: removeTags` | **Remove** a set of tags from notes. |

---

## Contributing & Feedback

This project is open source, and community feedback is highly welcome!

* **Report Bugs / Suggest Features:** Please use [GitHub Issues](https://github.com/AnkiProTools1/apro-bridge/issues).
* **General Discussion:** Use [GitHub Discussions](https://github.com/AnkiProTools1/apro-bridge/discussions) or join us on [Telegram](https://t.me/AnkiProTools).

## License 📄

Distributed under the GPLv3 License. See the `LICENSE` file for more information.
