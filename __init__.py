# Final corrected __init__.py (with detailed logging added)

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
    <p><b>Version:</b> 1.0</p>
    <p>
        <a href="https://www.ankiprotools.com/bridge">Website</a> |
        <a href="https://www.ankiprotools.com/donations">Donate</a>
    </p>
    """
    msg_box = QMessageBox()
    msg_box.setWindowTitle("About Apro - Bridge")
    # Correct way to set Rich Text format
    msg_box.setTextFormat(Qt.TextFormat.RichText)
    msg_box.setText(about_text)
    msg_box.exec() # Use exec() for modern Anki versions

# Updated RequestHandler Class (within __init__.py)
class RequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS, PATCH, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        print(f"\n{LOG_PREFIX} Received OPTIONS request for {self.path}") # LOG
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_DELETE(self):
        print(f"\n{LOG_PREFIX} Received DELETE request for {self.path}") # LOG
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length) # Read bytes
            print(f"{LOG_PREFIX} DELETE data: {body_bytes.decode('utf-8')}") # LOG data
            data = json.loads(body_bytes) # Parse after logging

            note_id = data.get('noteId')
            if not note_id:
                raise ValueError("Request was missing required field 'noteId'.")

            # --- Use mw.col.remove_notes directly for efficiency ---
            error_container = [None]
            task_done = Event()
            def delete_note_sync():
                try:
                    print(f"{LOG_PREFIX} [Main Thread] Deleting note {note_id}") # LOG
                    mw.col.remove_notes([note_id])
                    tooltip(f"✅ Apro - Bridge note {note_id} deleted")
                    print(f"{LOG_PREFIX} [Main Thread] Successfully deleted note {note_id}") # LOG
                except Exception as e:
                    error_container[0] = e
                finally:
                    task_done.set()

            mw.taskman.run_on_main(delete_note_sync)
            task_done.wait() # Wait for the main thread task

            if error_container[0]:
                raise error_container[0]

            print(f"{LOG_PREFIX} DELETE request for note {note_id} successful.") # LOG
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            # --- DETAILED ERROR LOG ---
            print(f"\n{LOG_PREFIX} === ERROR (DELETE) ===")
            print(error_message)
            print(f"{LOG_PREFIX} =========================\n")
            # --- End Error Log ---
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (DELETE):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)})

    def do_PATCH(self):
        print(f"\n{LOG_PREFIX} Received PATCH request for {self.path}") # LOG
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length) # Read bytes
            print(f"{LOG_PREFIX} PATCH data: {body_bytes.decode('utf-8')}") # LOG data
            data = json.loads(body_bytes) # Parse after logging

            # Allow direct 'note' object or standard AnkiConnect 'params' structure
            note_data = data.get('note') or data.get('params', {}).get('note')
            if not note_data:
                 raise ValueError("Request 'note' structure or 'params.note' structure missing.")

            note_id = note_data.get('id')
            fields_data = note_data.get('fields')

            if not note_id:
                raise ValueError("Request was missing required field 'id' within 'note'.")

            print(f"{LOG_PREFIX} Patching note {note_id} with fields: {fields_data}") # LOG

            # Proceed only if fields are present
            if fields_data is not None:
                if not isinstance(fields_data, dict):
                    raise ValueError("'fields' must be an object/dictionary.")

                error_container = [None]
                task_done = Event()
                def update_note_sync():
                    try:
                        print(f"{LOG_PREFIX} [Main Thread] Updating note {note_id}") # LOG
                        note = mw.col.get_note(note_id)
                        if not note:
                            # Send specific error back if note not found
                            raise ValueError(f"Note with ID '{note_id}' not found.")

                        # --- Use mw.col.update_note for better performance/hook handling ---
                        changed_fields = False
                        for field_name, field_value in fields_data.items():
                            if field_name in note:
                                if note[field_name] != field_value:
                                    note[field_name] = field_value
                                    changed_fields = True
                            else:
                                # Log warning but don't fail the whole request
                                print(f"{LOG_PREFIX} Warning: Field '{field_name}' not found in Note Type for note {note_id}.")

                        if changed_fields:
                            mw.col.update_note(note) # Preferred method
                            tooltip(f"✅ Apro - Bridge note {note_id} fields updated")
                            print(f"{LOG_PREFIX} [Main Thread] Successfully updated fields for note {note_id}") # LOG
                        else:
                            tooltip(f"ℹ️ Apro - Bridge note {note_id} fields had no changes")
                            print(f"{LOG_PREFIX} [Main Thread] No field changes detected for note {note_id}") # LOG
                    except Exception as e:
                        error_container[0] = e
                    finally:
                        task_done.set()

                mw.taskman.run_on_main(update_note_sync)
                task_done.wait() # Wait for the main thread task

                if error_container[0]:
                    # Specific check for note not found
                    if "not found" in str(error_container[0]):
                         self._send_error(404, {"error": str(error_container[0]), "status": "not found"}) # Send 404
                         return
                    else:
                        raise error_container[0] # Raise other errors
            else:
                # If only 'id' was provided without 'fields', it's a valid PATCH but does nothing
                print(f"{LOG_PREFIX} PATCH request for note {note_id} received (no 'fields' key). No action taken.") # LOG
                pass

            print(f"{LOG_PREFIX} PATCH request for note {note_id} successful.") # LOG
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"result": None, "error": None}).encode('utf-8')) # Use standard AnkiConnect response format
        except Exception as e:
            error_message = traceback.format_exc()
            # --- DETAILED ERROR LOG ---
            print(f"\n{LOG_PREFIX} === ERROR (PATCH) ===")
            print(error_message)
            print(f"{LOG_PREFIX} =========================\n")
            # --- End Error Log ---
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (PATCH):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)}) # Default to 400 for other errors


    def do_PUT(self):
        print(f"\n{LOG_PREFIX} Received PUT (media upload) request for {self.path}") # LOG
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length)
            # DO NOT log raw body_bytes, it's huge (base64 media)
            data = json.loads(body_bytes.decode('utf-8'))
            b64_data = data.get('mediaData')
            extension = data.get('extension', 'unknown')

            # Log metadata, not the data itself
            media_data_preview = (b64_data[:30] + '...') if b64_data else 'None'
            print(f"{LOG_PREFIX} PUT data: extension='{extension}', mediaData (preview)='{media_data_preview}'") # LOG

            if not b64_data:
                raise ValueError("Missing 'mediaData' field.")

            media_bytes = base64.b64decode(b64_data)
            hasher = hashlib.sha1()
            hasher.update(media_bytes)
            # Use underscore filename if needed by Anki version
            # filename = f"_apro-bridge-{hasher.hexdigest()}.{extension}"
            filename = f"apro-bridge-{hasher.hexdigest()}.{extension}"

            print(f"{LOG_PREFIX} Writing media data to file: {filename}") # LOG
            final_filename = mw.col.media.write_data(filename, media_bytes)
            print(f"{LOG_PREFIX} Successfully wrote media to: {final_filename}") # LOG

            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            # Send standard response format
            self.wfile.write(json.dumps({"result": final_filename, "error": None}).encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            # --- DETAILED ERROR LOG ---
            print(f"\n{LOG_PREFIX} === ERROR (PUT) ===")
            print(error_message)
            print(f"{LOG_PREFIX} =========================\n")
            # --- End Error Log ---
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (PUT):\n{error_message}", period=10000))
            self._send_error(500, {"error": str(e)}) # Use 500 for server-side media errors


    def do_GET(self):
        print(f"\n{LOG_PREFIX} Received GET request for {self.path}") # LOG
        try:
            parsed_path = urlparse(self.path)
            query = parse_qs(parsed_path.query)
            print(f"{LOG_PREFIX} GET query params: {query}") # LOG
            response_data = {}

            if parsed_path.path == '/model-fields':
                model_name = query.get('modelName', [None])[0]
                print(f"{LOG_PREFIX} GET action: /model-fields for model: {model_name}") # LOG
                if not model_name: raise ValueError("modelName parameter is required")
                model = mw.col.models.by_name(model_name)
                if not model: raise ValueError(f"Model '{model_name}' not found")

                fields = [f['name'] for f in model['flds']]
                is_cloze = model['type'] == 1 # CLOZE_MODEL == 1
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
                     # Find the field used in the first {{cloze: ...}} tag
                    combined_template = front_template + back_template
                    match = re.search(r"\{\{cloze:(.*?)\}\}", combined_template)
                    if match:
                        cloze_field_name = match.group(1)

                print(f"{LOG_PREFIX} Found model fields. isCloze={is_cloze}, clozeField={cloze_field_name}") # LOG

                response_data = {
                    "result": { # Wrap in 'result' for standard format
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
                print(f"{LOG_PREFIX} GET action: / (root)") # LOG
                 # Assume root request returns basic info
                deck_names = sorted([d['name'] for d in mw.col.decks.all()])
                note_type_names = sorted([m.name for m in mw.col.models.all_names_and_ids()])
                response_data = {"result": {"decks": deck_names, "noteTypes": note_type_names}, "error": None}

            print(f"{LOG_PREFIX} GET request successful.") # LOG
            response_json = json.dumps(response_data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
        except Exception as e:
            error_message = traceback.format_exc()
            # --- DETAILED ERROR LOG ---
            print(f"\n{LOG_PREFIX} === ERROR (GET) ===")
            print(error_message)
            print(f"{LOG_PREFIX} =========================\n")
            # --- End Error Log ---
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (GET):\n{error_message}", period=10000))
            self._send_error(500, {"error": str(e)}) # Use 500 for server errors on GET


    def do_POST(self):
        print(f"\n{LOG_PREFIX} Received POST request for {self.path}") # LOG
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body_bytes = self.rfile.read(content_length) # Read bytes
            print(f"{LOG_PREFIX} POST data: {body_bytes.decode('utf-8')}") # LOG data
            data = json.loads(body_bytes) # Parse after logging

            action = data.get('action')
            params = data.get('params', {})
            version = data.get('version')

            print(f"{LOG_PREFIX} POST action: {action}, params: {params}") # LOG

            # --- Route based on action ---
            if action == 'notesInfo':
                print(f"{LOG_PREFIX} POST routing to: handle_notes_info") # LOG
                self.handle_notes_info(params)
            elif action == 'addTags':
                print(f"{LOG_PREFIX} POST routing to: handle_add_tags") # LOG
                self.handle_add_tags(params)
            elif action == 'removeTags':
                print(f"{LOG_PREFIX} POST routing to: handle_remove_tags") # LOG
                self.handle_remove_tags(params)
            # --- NEW: Add handler for updateNoteTags ---
            elif action == 'updateNoteTags':
                print(f"{LOG_PREFIX} POST routing to: handle_update_note_tags") # LOG
                self.handle_update_note_tags(params)
            # ------------------------------------------
            # --- Default: Original Add Note functionality ---
            elif action is None and 'deck' in data: # Check for original add note format
                print(f"{LOG_PREFIX} POST routing to: handle_add_note (legacy format)") # LOG
                self.handle_add_note(data)
            else:
                # --- Handle other potential AnkiConnect actions or send error ---
                 raise ValueError(f"Unsupported action: {action}")

        except Exception as e:
            error_message = traceback.format_exc()
            # --- DETAILED ERROR LOG ---
            print(f"\n{LOG_PREFIX} === ERROR (POST) ===")
            print(error_message)
            print(f"{LOG_PREFIX} =========================\n")
            # --- End Error Log ---
            mw.taskman.run_on_main(lambda: tooltip(f"Apro - Bridge Connector Error (POST):\n{error_message}", period=10000))
            self._send_error(400, {"error": str(e)})

    # --- NEW: Handler for updateNoteTags ---
    def handle_update_note_tags(self, params):
        print(f"{LOG_PREFIX} Handling action: updateNoteTags") # LOG
        note_data = params.get('note')
        if not note_data or not isinstance(note_data, dict):
            raise ValueError("'note' parameter object is required for updateNoteTags.")

        note_id = note_data.get('id')
        tags_str = note_data.get('tags') # Expects a single space-separated string

        if note_id is None or tags_str is None: # tags_str can be empty, but must be present
             raise ValueError("'note.id' and 'note.tags' (space-separated string) are required.")

        new_tags_list = tags_str.split() # Split into a list for Anki

        error_container = [None]
        task_done = Event()

        def update_tags_sync():
            try:
                print(f"{LOG_PREFIX} [Main Thread] updateNoteTags: Updating tags for note {note_id} to: {new_tags_list}") # LOG
                note = mw.col.get_note(note_id)
                if not note:
                    raise ValueError(f"Note {note_id} not found during updateNoteTags.")

                # Check if tags actually need changing to avoid unnecessary updates
                # Convert both to sets for comparison
                current_tags_set = set(note.tags)
                new_tags_set = set(new_tags_list)

                if current_tags_set != new_tags_set:
                    note.tags = new_tags_list # Directly assign the new list
                    mw.col.update_note(note)
                    tooltip(f"✅ Apro - Bridge tags updated for note {note_id}")
                    print(f"{LOG_PREFIX} [Main Thread] updateNoteTags: Successfully updated tags for note {note_id}.") # LOG
                else:
                    tooltip(f"ℹ️ Apro - Bridge tags for note {note_id} had no changes")
                    print(f"{LOG_PREFIX} [Main Thread] updateNoteTags: Tags for note {note_id} already match. No update needed.") # LOG

            except Exception as e:
                print(f"{LOG_PREFIX} [Main Thread] updateNoteTags: EXCEPTION: {traceback.format_exc()}") # Log error
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(update_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        print(f"{LOG_PREFIX} updateNoteTags action successful for note {note_id}.") # LOG
        self._send_response(200, {"result": None, "error": None}) # Standard success response
    
    # --- UPDATED: Handler for notesInfo with more logging ---
    def handle_notes_info(self, params):
        print(f"{LOG_PREFIX} Handling action: notesInfo") # LOG
        note_ids = params.get('notes')
        if not note_ids or not isinstance(note_ids, list):
            raise ValueError("'notes' parameter (a list of note IDs) is required for notesInfo.")

        results_container = [None]
        error_container = [None]
        task_done = Event()

        def get_notes_info_sync():
            try:
                print(f"{LOG_PREFIX} [Main Thread] notesInfo: Getting info for notes: {note_ids}") # LOG
                results = []
                # --- DEBUG LOG: Find notes using Anki's method ---
                notes_found = mw.col.find_notes(f"nid:{','.join(map(str, note_ids))}")
                print(f"{LOG_PREFIX} [Main Thread] notesInfo: mw.col.find_notes found IDs: {notes_found}") # LOG

                # --- DEBUG LOG: Get note objects one by one and log details ---
                for nid in note_ids:
                    print(f"{LOG_PREFIX} [Main Thread] notesInfo: Attempting mw.col.get_note({nid})") # LOG
                    note = mw.col.get_note(nid)
                    if note:
                        # --- ADD THIS LINE ---
                        note.load() # Explicitly reload note data from DB
                        # ---------------------

                        # --- DETAILED LOG for found note ---
                        print(f"{LOG_PREFIX} [Main Thread] notesInfo: Found note {nid}.")
                        print(f"{LOG_PREFIX} [Main Thread] notesInfo:   -> Note Object Type: {type(note)}")
                        print(f"{LOG_PREFIX} [Main Thread] notesInfo:   -> Note Tags BEFORE adding to result: {note.tags}")
                        print(f"{LOG_PREFIX} [Main Thread] notesInfo:   -> Note Fields (items): {list(note.items())}")
                        # ------------------------------------
                        results.append({
                            "noteId": note.id,
                            "tags": note.tags, # Direct access
                            "fields": { fn: {"value": fv, "order": idx} for idx, (fn, fv) in enumerate(note.items())},
                            "modelName": note.note_type()['name'],
                            "cards": mw.col.card_ids_of_note(nid)
                        })
                    else:
                        print(f"{LOG_PREFIX} [Main Thread] notesInfo: Note {nid} NOT FOUND by mw.col.get_note.") # LOG
                        results.append(None) # Indicate note not found

                # --- DEBUG LOG: Log the final constructed results list before setting it ---
                print(f"{LOG_PREFIX} [Main Thread] notesInfo: Final results list constructed: {results}") # LOG
                results_container[0] = results
            except Exception as e:
                # --- DEBUG LOG: Log any exception during note processing ---
                print(f"{LOG_PREFIX} [Main Thread] notesInfo: EXCEPTION during processing: {traceback.format_exc()}") # DETAILED LOG
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(get_notes_info_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        print(f"{LOG_PREFIX} notesInfo action successful.") # LOG
        self._send_response(200, {"result": results_container[0], "error": None})


    # --- Handler for addTags ---
    def handle_add_tags(self, params):
        print(f"{LOG_PREFIX} Handling action: addTags") # LOG
        note_ids = params.get('notes')
        tags_str = params.get('tags')
        if not note_ids or not isinstance(note_ids, list) or tags_str is None or not isinstance(tags_str, str):
            raise ValueError("'notes' (list of IDs) and 'tags' (space-separated string) are required for addTags.")

        tags_to_add = tags_str.split()
        if not tags_to_add:
             print(f"{LOG_PREFIX} addTags action: No tags to add.") # LOG
             self._send_response(200, {"result": None, "error": None}) # Nothing to add
             return

        error_container = [None]
        notes_changed_count = [0] # Keep track of actual changes
        task_done = Event()

        def add_tags_sync():
            try:
                print(f"{LOG_PREFIX} [Main Thread] Adding tags '{tags_str}' to notes: {note_ids}") # LOG
                notes_processed = 0
                for nid in note_ids:
                    note = mw.col.get_note(nid)
                    if not note:
                        print(f"{LOG_PREFIX} Warning: Note {nid} not found during addTags.")
                        continue # Skip to next note if not found

                    note_changed = False
                    for tag in tags_to_add:
                         # note.add_tag handles duplicates gracefully
                        if note.add_tag(tag):
                             note_changed = True

                    if note_changed:
                        mw.col.update_note(note) # Use update_note instead of flush
                        notes_changed_count[0] += 1
                    notes_processed += 1

                tooltip(f"✅ Apro - Bridge updated tags on {notes_changed_count[0]} of {notes_processed} note(s)")
                print(f"{LOG_PREFIX} [Main Thread] Finished adding tags. {notes_changed_count[0]} notes changed.") # LOG
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(add_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        print(f"{LOG_PREFIX} addTags action successful.") # LOG
        self._send_response(200, {"result": None, "error": None})

    # --- Handler for removeTags ---
    def handle_remove_tags(self, params):
        print(f"{LOG_PREFIX} Handling action: removeTags") # LOG
        note_ids = params.get('notes')
        tags_str = params.get('tags')
        if not note_ids or not isinstance(note_ids, list) or tags_str is None or not isinstance(tags_str, str):
             raise ValueError("'notes' (list of IDs) and 'tags' (space-separated string) are required for removeTags.")

        tags_to_remove = tags_str.split()
        if not tags_to_remove:
             print(f"{LOG_PREFIX} removeTags action: No tags to remove.") # LOG
             self._send_response(200, {"result": None, "error": None}) # Nothing to remove
             return

        error_container = [None]
        notes_changed_count = [0] # Keep track of actual changes
        task_done = Event()

        def remove_tags_sync():
            try:
                print(f"{LOG_PREFIX} [Main Thread] Removing tags '{tags_str}' from notes: {note_ids}") # LOG
                notes_processed = 0
                for nid in note_ids:
                    note = mw.col.get_note(nid)
                    if not note:
                        print(f"{LOG_PREFIX} Warning: Note {nid} not found during removeTags.")
                        continue # Skip to next note if not found

                    note_changed = False
                    for tag in tags_to_remove:
                        # Use remove_tag, check if it existed before removing
                        if tag in note.tags:
                             note.remove_tag(tag) # Use remove_tag (more standard than del_tag now)
                             note_changed = True

                    if note_changed:
                        mw.col.update_note(note) # Use update_note instead of flush
                        notes_changed_count[0] += 1
                    notes_processed += 1

                tooltip(f"✅ Apro - Bridge updated tags on {notes_changed_count[0]} of {notes_processed} note(s)")
                print(f"{LOG_PREFIX} [Main Thread] Finished removing tags. {notes_changed_count[0]} notes changed.") # LOG
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(remove_tags_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        print(f"{LOG_PREFIX} removeTags action successful.") # LOG
        self._send_response(200, {"result": None, "error": None})

    # --- Original Add Note logic, now in its own handler ---
    def handle_add_note(self, data):
        print(f"{LOG_PREFIX} Handling action: addNote (legacy)") # LOG
        deck_name = data.get('deck')
        model_name = data.get('noteType')
        fields_data = data.get('fields')
        tags_list = data.get('tags', []) # Expects a list here

        print(f"{LOG_PREFIX} Attempting to add note to deck '{deck_name}' with model '{model_name}'") # LOG

        if not all([deck_name, model_name, fields_data]):
            raise ValueError("Request was missing required fields (deck, noteType, or fields).")

        note_id_container = [None]
        error_container = [None]
        task_done = Event()

        def add_note_sync():
            try:
                print(f"{LOG_PREFIX} [Main Thread] Creating note for deck '{deck_name}'") # LOG
                model = mw.col.models.by_name(model_name)
                if not model:
                    raise ValueError(f"Note Type '{model_name}' not found in Anki.")

                note = Note(mw.col, model)

                for field_name, field_value in fields_data.items():
                    if field_name in note:
                        note[field_name] = field_value
                    else:
                        # Log warning, but don't fail the whole add operation
                        print(f"{LOG_PREFIX} Warning: Field '{field_name}' not found in Note Type '{model_name}' during note creation.")
                        # raise ValueError(f"Field '{field_name}' not found in Note Type '{model_name}'.")

                if isinstance(tags_list, list):
                    for tag in tags_list:
                        if isinstance(tag, str):
                            note.add_tag(tag.strip())
                else:
                    print(f"{LOG_PREFIX} Warning: 'tags' field was not a list for note being added to '{deck_name}'.")


                # Ensure deck exists, create if not? (Anki default behavior)
                did = mw.col.decks.id(deck_name)
                mw.col.add_note(note, did)
                note_id_container[0] = note.id
                tooltip(f"✅ Apro - Bridge note added to {deck_name}")
                print(f"{LOG_PREFIX} [Main Thread] Successfully added note {note.id} to deck '{deck_name}'") # LOG
            except Exception as e:
                error_container[0] = e
            finally:
                task_done.set()

        mw.taskman.run_on_main(add_note_sync)
        task_done.wait()

        if error_container[0]:
            raise error_container[0]

        print(f"{LOG_PREFIX} addNote (legacy) action successful. New Note ID: {note_id_container[0]}") # LOG
        # Use standard AnkiConnect success format
        self._send_response(200, {"result": note_id_container[0], "error": None})

    # --- Helper to send standard JSON responses ---
    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    # --- Helper to send standard JSON error responses ---
    def _send_error(self, status_code, error_data):
         # Ensure error data follows {"error": "message"} format
        if "error" not in error_data:
             error_data = {"error": str(error_data)} # Basic conversion if needed
        error_data["result"] = None # Add null result for consistency
        self._send_response(status_code, error_data)


    # --- Modified log_message to print to console for debugging ---
    def log_message(self, format, *args):
        print(f"{LOG_PREFIX} HTTP: {format % args}")
        # return # <-- Muted previously

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
        print(f"{LOG_PREFIX} Starting server on {HOST}:{PORT}...") # LOG
        server_thread = ServerThread()
        server_thread.daemon = True
        server_thread.start()
        print(f"{LOG_PREFIX} Server thread started.") # LOG
    else:
        print(f"{LOG_PREFIX} Server already running.") # LOG

def stop_server():
    global server_thread
    if server_thread is not None:
        print(f"{LOG_PREFIX} Stopping server...") # LOG
        server_thread.stop()
        server_thread = None
        print(f"{LOG_PREFIX} Server stopped.") # LOG
    else:
        print(f"{LOG_PREFIX} Server not running.") # LOG

def setup_menu():
    # Creates a clickable action
    action = QAction("About Apro - Bridge", mw)
    action.triggered.connect(show_about_window)
    # Adds the action directly to the Tools menu
    mw.form.menuTools.addAction(action)

addHook("profileLoaded", start_server)
addHook("profileLoaded", setup_menu)
addHook("unloadProfile", stop_server)