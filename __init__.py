# Final corrected __init__.py (with detailed logging and findNotes added)

import json
import threading
import base64
import hashlib
import traceback
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from threading import Event

from aqt import mw
from aqt.utils import tooltip
from anki.notes import Note
from anki.hooks import addHook
from aqt.qt import QAction, QMessageBox, Qt

LOG_PREFIX = "Apro-Bridge-Log:" # Added for easy log filtering
HOST = 'localhost'
PORT = 8767

def show_about_window():
    about_text = """
    <h2>Apro - Bridge</h2>
    <p>Developed by AnkiProTools.com</p>
    <p>This add-on acts as a bridge between Anki and other applications like CineCard and Synapse, allowing you to quickly create and manage your Anki cards from external sources.</p>
    <p><b>Version:</b> 1.1 (Added findNotes)</p>
    <p>
        <a href="https://www.ankiprotools.com/bridge">Website</a> |
        <a href="https://www.ankiprotools.com/donations">Donate</a>
    </p>
    """
    msg_box = QMessageBox()
    msg_box.setWindowTitle("About Apro - Bridge")
    msg_box.setTextFormat(Qt.TextFormat.RichText)
    msg_box.setText(about_text)
    msg_box.exec()

class RequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS, PATCH, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        print(f"\n{LOG_PREFIX} Received OPTIONS request for {self.path}")
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_DELETE(self):
        print(f"\n{LOG_PREFIX} Received DELETE request for {self.path}")
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes)

            note_id = data.get('noteId')
            if not note_id:
                raise ValueError("Request was missing required field 'noteId'.")

            error_container = [None]
            task_done = Event()
            def delete_note_sync():
                try:
                    mw.col.remove_notes([note_id])
                    tooltip(f"✅ Apro - Bridge note {note_id} deleted")
                except Exception as e:
                    error_container[0] = e
                finally:
                    task_done.set()

            mw.taskman.run_on_main(delete_note_sync)
            task_done.wait()

            if error_container[0]:
                raise error_container[0]

            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (DELETE):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)})

    def do_PATCH(self):
        print(f"\n{LOG_PREFIX} Received PATCH request for {self.path}")
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes)

            note_data = data.get('note') or data.get('params', {}).get('note')
            if not note_data:
                 raise ValueError("Request 'note' structure or 'params.note' structure missing.")

            note_id = note_data.get('id')
            fields_data = note_data.get('fields')

            if not note_id:
                raise ValueError("Request was missing required field 'id' within 'note'.")

            if fields_data is not None:
                if not isinstance(fields_data, dict):
                    raise ValueError("'fields' must be an object/dictionary.")

                error_container = [None]
                task_done = Event()
                def update_note_sync():
                    try:
                        note = mw.col.get_note(note_id)
                        if not note:
                            raise ValueError(f"Note with ID '{note_id}' not found.")

                        changed_fields = False
                        for field_name, field_value in fields_data.items():
                            if field_name in note:
                                if note[field_name] != field_value:
                                    note[field_name] = field_value
                                    changed_fields = True

                        if changed_fields:
                            mw.col.update_note(note)
                            tooltip(f"✅ Apro - Bridge note {note_id} fields updated")
                    except Exception as e:
                        error_container[0] = e
                    finally:
                        task_done.set()

                mw.taskman.run_on_main(update_note_sync)
                task_done.wait()

                if error_container[0]:
                    if "not found" in str(error_container[0]):
                         self._send_error(404, {"error": str(error_container[0]), "status": "not found"})
                         return
                    else:
                        raise error_container[0]
            else:
                pass

            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"result": None, "error": None}).encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (PATCH):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)})

    def do_PUT(self):
        print(f"\n{LOG_PREFIX} Received PUT (media upload) request for {self.path}")
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes.decode('utf-8'))
            b64_data = data.get('mediaData')
            extension = data.get('extension', 'unknown')

            if not b64_data:
                raise ValueError("Missing 'mediaData' field.")

            media_bytes = base64.b64decode(b64_data)
            hasher = hashlib.sha1()
            hasher.update(media_bytes)
            filename = f"apro-bridge-{hasher.hexdigest()}.{extension}"

            final_filename = mw.col.media.write_data(filename, media_bytes)

            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"result": final_filename, "error": None}).encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (PUT):\n{error_message}", period=10000))
            self._send_error(500, {"error": str(e)})

    def do_GET(self):
        print(f"\n{LOG_PREFIX} Received GET request for {self.path}")
        try:
            parsed_path = urlparse(self.path)
            query = parse_qs(parsed_path.query)
            response_data = {}

            if parsed_path.path == '/model-fields':
                model_name = query.get('modelName', [None])[0]
                if not model_name: raise ValueError("modelName parameter is required")
                model = mw.col.models.by_name(model_name)
                if not model: raise ValueError(f"Model '{model_name}' not found")

                fields = [f['name'] for f in model['flds']]
                is_cloze = model['type'] == 1
                cloze_field_name = None
                front_template = ""
                back_template = ""
                css = model.get('css', '')

                templates = model.get('tmpls', [])
                if templates:
                    first_template = templates[0]
                    front_template = first_template.get('qfmt', '')
                    back_template = first_template.get('afmt', '')

                if is_cloze:
                    combined_template = front_template + back_template
                    match = re.search(r"\{\{cloze:(.*?)\}\}", combined_template)
                    if match:
                        cloze_field_name = match.group(1)

                response_data = {
                    "result": {
                        "name": model['name'],
                        "fields": fields,
                        "isCloze": is_cloze,
                        "clozeFieldName": cloze_field_name,
                        "Front": front_template,
                        "Back": back_template,
                        "CSS": css
                    },
                    "error": None
                }
            else:
                deck_names = sorted([d['name'] for d in mw.col.decks.all()])
                note_type_names = sorted([m.name for m in mw.col.models.all_names_and_ids()])
                response_data = {"result": {"decks": deck_names, "noteTypes": note_type_names}, "error": None}

            response_json = json.dumps(response_data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (GET):\n{error_message}", period=10000))
            self._send_error(500, {"error": str(e)})


    def do_POST(self):
        print(f"\n{LOG_PREFIX} Received POST request for {self.path}")
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes)

            action = data.get('action')
            params = data.get('params', {})

            if action == 'notesInfo':
                self.handle_notes_info(params)
            elif action == 'addTags':
                self.handle_add_tags(params)
            elif action == 'removeTags':
                self.handle_remove_tags(params)
            elif action == 'updateNoteTags':
                self.handle_update_note_tags(params)
            # --- NEW: Added handler for findNotes ---
            elif action == 'findNotes':
                self.handle_find_notes(params)
            # ----------------------------------------
            elif action is None and 'deck' in data:
                self.handle_add_note(data)
            else:
                 raise ValueError(f"Unsupported action: {action}")

        except Exception as e:
            error_message = traceback.format_exc()
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (POST):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)})

    # --- NEW: Handler for findNotes ---
    def handle_find_notes(self, params):
        query = params.get('query')
        if query is None or not isinstance(query, str):
             raise ValueError("'query' parameter (a string) is required for findNotes.")

        results_container = [None]
        error_container = [None]
        task_done = Event()

        def find_notes_sync():
            try:
                found_ids = mw.col.find_notes(query)
                results_container[0] = list(found_ids)
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(find_notes_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        self._send_response(200, {"result": results_container[0], "error": None})


    def handle_update_note_tags(self, params):
        note_data = params.get('note')
        if not note_data or not isinstance(note_data, dict):
            raise ValueError("'note' parameter object is required for updateNoteTags.")

        note_id = note_data.get('id')
        tags_str = note_data.get('tags')

        if note_id is None or tags_str is None:
             raise ValueError("'note.id' and 'note.tags' (space-separated string) are required.")

        new_tags_list = tags_str.split()
        error_container = [None]
        task_done = Event()

        def update_tags_sync():
            try:
                note = mw.col.get_note(note_id)
                if not note:
                    raise ValueError(f"Note {note_id} not found during updateNoteTags.")

                current_tags_set = set(note.tags)
                new_tags_set = set(new_tags_list)

                if current_tags_set != new_tags_set:
                    note.tags = new_tags_list
                    mw.col.update_note(note)
                    tooltip(f"✅ Apro - Bridge tags updated for note {note_id}")
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(update_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        self._send_response(200, {"result": None, "error": None})
    
    def handle_notes_info(self, params):
        note_ids = params.get('notes')
        if not note_ids or not isinstance(note_ids, list):
            raise ValueError("'notes' parameter (a list of note IDs) is required for notesInfo.")

        results_container = [None]
        error_container = [None]
        task_done = Event()

        def get_notes_info_sync():
            try:
                results = []
                for nid in note_ids:
                    note = mw.col.get_note(nid)
                    if note:
                        note.load()
                        results.append({
                            "noteId": note.id,
                            "tags": note.tags,
                            "fields": { fn: {"value": fv, "order": idx} for idx, (fn, fv) in enumerate(note.items())},
                            "modelName": note.note_type()['name'],
                            "cards": mw.col.card_ids_of_note(nid)
                        })
                    else:
                        results.append(None)
                results_container[0] = results
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(get_notes_info_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        self._send_response(200, {"result": results_container[0], "error": None})

    def handle_add_tags(self, params):
        note_ids = params.get('notes')
        tags_str = params.get('tags')
        if not note_ids or not isinstance(note_ids, list) or tags_str is None or not isinstance(tags_str, str):
            raise ValueError("'notes' (list of IDs) and 'tags' (space-separated string) are required for addTags.")

        tags_to_add = tags_str.split()
        if not tags_to_add:
             self._send_response(200, {"result": None, "error": None})
             return

        error_container = [None]
        notes_changed_count = [0]
        task_done = Event()

        def add_tags_sync():
            try:
                notes_processed = 0
                for nid in note_ids:
                    note = mw.col.get_note(nid)
                    if not note: continue

                    note_changed = False
                    for tag in tags_to_add:
                        if note.add_tag(tag): note_changed = True

                    if note_changed:
                        mw.col.update_note(note)
                        notes_changed_count[0] += 1
                    notes_processed += 1

                tooltip(f"✅ Apro - Bridge updated tags on {notes_changed_count[0]} of {notes_processed} note(s)")
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(add_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        self._send_response(200, {"result": None, "error": None})

    def handle_remove_tags(self, params):
        note_ids = params.get('notes')
        tags_str = params.get('tags')
        if not note_ids or not isinstance(note_ids, list) or tags_str is None or not isinstance(tags_str, str):
             raise ValueError("'notes' (list of IDs) and 'tags' (space-separated string) are required for removeTags.")

        tags_to_remove = tags_str.split()
        if not tags_to_remove:
             self._send_response(200, {"result": None, "error": None})
             return

        error_container = [None]
        notes_changed_count = [0]
        task_done = Event()

        def remove_tags_sync():
            try:
                notes_processed = 0
                for nid in note_ids:
                    note = mw.col.get_note(nid)
                    if not note: continue

                    note_changed = False
                    for tag in tags_to_remove:
                        if tag in note.tags:
                             note.remove_tag(tag)
                             note_changed = True

                    if note_changed:
                        mw.col.update_note(note)
                        notes_changed_count[0] += 1
                    notes_processed += 1
                tooltip(f"✅ Apro - Bridge updated tags on {notes_changed_count[0]} of {notes_processed} note(s)")
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(remove_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]
        self._send_response(200, {"result": None, "error": None})

    def handle_add_note(self, data):
        deck_name = data.get('deck')
        model_name = data.get('noteType')
        fields_data = data.get('fields')
        tags_list = data.get('tags', [])

        if not all([deck_name, model_name, fields_data]):
            raise ValueError("Request was missing required fields (deck, noteType, or fields).")

        note_id_container = [None]
        error_container = [None]
        task_done = Event()

        def add_note_sync():
            try:
                model = mw.col.models.by_name(model_name)
                if not model: raise ValueError(f"Note Type '{model_name}' not found in Anki.")
                note = Note(mw.col, model)
                for field_name, field_value in fields_data.items():
                    if field_name in note: note[field_name] = field_value
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        if isinstance(tag, str): note.add_tag(tag.strip())
                did = mw.col.decks.id(deck_name)
                mw.col.add_note(note, did)
                note_id_container[0] = note.id
                tooltip(f"✅ Apro - Bridge note added to {deck_name}")
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(add_note_sync)
        task_done.wait()

        if error_container[0]: raise error_container[0]
        self._send_response(200, {"result": note_id_container[0], "error": None})

    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_error(self, status_code, error_data):
        if "error" not in error_data: error_data = {"error": str(error_data)}
        error_data["result"] = None
        self._send_response(status_code, error_data)

    def log_message(self, format, *args):
        print(f"{LOG_PREFIX} HTTP: {format % args}")

class ServerThread(threading.Thread):
    def run(self):
        self.server = HTTPServer((HOST, PORT), RequestHandler)
        self.server.serve_forever()
    def stop(self):
        self.server.shutdown()
        self.server.server_close()
server_thread = None
def start_server():
    global server_thread
    if server_thread is None:
        server_thread = ServerThread()
        server_thread.daemon = True
        server_thread.start()

def stop_server():
    global server_thread
    if server_thread is not None:
        server_thread.stop()
        server_thread = None

def setup_menu():
    action = QAction("About Apro - Bridge", mw)
    action.triggered.connect(show_about_window)
    mw.form.menuTools.addAction(action)

addHook("profileLoaded", start_server)
addHook("profileLoaded", setup_menu)
addHook("unloadProfile", stop_server)
