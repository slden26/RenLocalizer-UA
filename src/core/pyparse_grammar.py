"""
Lightweight, SDK-free Ren'Py grammar built around a state machine and indentation.

Goals:
- No Ren'Py SDK dependency
- Robust triple-quote handling (paragraph split)
- Menu/screen/python/_() coverage with placeholder preservation
- Logical line joining (line continuation with backslash)
"""
from typing import List, Dict


def extract_with_pyparsing(content: str, file_path: str = "") -> List[Dict]:
    """
    "Pyparsing" adı kalsa da, burada indentation tabanlı bir state machine var.
    Ren'Py SDK yüklenmeden diyalog/menü/screen/_() metinlerini çıkarır.
    """
    try:  # Optional perf boost if pyparsing yüklü
        from pyparsing import ParserElement

        ParserElement.setDefaultWhitespaceChars(" \t")
        ParserElement.enablePackrat()
    except Exception:
        pass

    import re

    entries: List[Dict] = []

    TECHNICAL_PREFIXES = (
        "image ",
        "define ",
        "default ",
        "transform ",
        "style ",
        "config.",
        "gui.",
        "store.",
        "layout.",
        "label hide",
    )

    dialog_re = re.compile(
        r'^(?P<char>[A-Za-z_]\w*)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
    )
    narrator_re = re.compile(r'^(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
    menu_choice_re = re.compile(
        r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:if\s+[^:]+)?\s*:\s*$'
    )
    screen_elem_re = re.compile(
        r'\b(text|label|tooltip|textbutton)\s+(?:_\s*\(\s*)?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?:\s*\))?'
    )
    python_call_re = re.compile(
        r'(?:__|_)\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
    )
    notify_call_re = re.compile(
        r'renpy\.(?:say|notify)\s*\(\s*(?:[A-Za-z_]\w*\s*,\s*)?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
    )
    text_displayable_re = re.compile(
        r'\bText\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
    )
    input_call_re = re.compile(
        r'renpy\.input\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
    )
    triple_start_re = re.compile(
        r'^(?P<prefix>(?:[A-Za-z_]\w*\s+)?)(?P<delim>"""|\'\'\')(?P<body>.*)$'
    )

    def protect_placeholders(text: str):
        # NEW v2.4.1: Nested interpolation protection (e.g. [[var]])
        nested_var_pat = re.compile(r'\[{2,}[^\]]+\]{2,}')
        
        var_pat = re.compile(r"\[[^\[\]]+\]")
        tag_pat = re.compile(r"\{[^{}]+\}")
        
        # NEW v2.4.1: Ren'Py text tags with values (e.g. {size=30}, {b})
        renpy_tag_pat = re.compile(r'\{/?[a-z]+(?:=[^}]*)?\}')
        
        placeholders = {}
        counter = 0

        def repl(m):
            nonlocal counter
            key = f"__PH_{counter}__"
            placeholders[key] = m.group(0)
            counter += 1
            return key

        # Apply in order: nested first, then regular
        protected = nested_var_pat.sub(repl, text)
        protected = var_pat.sub(repl, protected)
        protected = tag_pat.sub(repl, protected)
        protected = renpy_tag_pat.sub(repl, protected)
        
        return protected, placeholders

    def restore_placeholders(text: str, placeholders: Dict[str, str]):
        for k, v in placeholders.items():
            text = text.replace(k, v)
        return text

    # Satır devamı (\) birleştirme
    logical_lines = []
    buffer = ""
    for line in content.splitlines():
        if line.rstrip().endswith("\\"):
            buffer += line.rstrip()[:-1] + " "
            continue
        if buffer:
            line = buffer + line
            buffer = ""
        logical_lines.append(line)
    if buffer:
        logical_lines.append(buffer)

    context_stack: List[tuple] = []  # (name, indent)
    triple_buffer = None  # (delim, start_idx, collected_str)

    def current_context_path() -> List[str]:
        return [c[0] for c in context_stack]

    for idx, line in enumerate(logical_lines):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Context pop
        while context_stack and indent < context_stack[-1][1]:
            context_stack.pop()

        # Triple quote devam
        if triple_buffer:
            delim, start_idx, collected = triple_buffer
            collected += ("\n" if collected else "") + stripped
            if delim in stripped:
                body, _, _ = collected.partition(delim)
                for para in body.split("\n\n"):
                    text = para.strip()
                    if not text:
                        continue
                    protected, ph = protect_placeholders(text)
                    entries.append(
                        {
                            "text": restore_placeholders(protected, ph),
                            "raw_text": f"{delim}" + body + f"{delim}",
                            "line_number": start_idx + 1,
                            "context_line": text,
                            "text_type": "monologue",
                            "file_path": file_path,
                            "context_path": current_context_path(),
                        }
                    )
                triple_buffer = None
            else:
                triple_buffer = (delim, start_idx, collected)
            continue

        if not stripped or stripped.startswith("#") or any(
            stripped.startswith(p) for p in TECHNICAL_PREFIXES
        ):
            continue

        # Skip translate blocks (already translated content) - v2.4.1
        if stripped.startswith("translate "):
            # Enter translate block - skip until dedent
            context_stack.append(("translate", indent))
            continue
        
        # If we're in a translate block, skip content until we exit
        if context_stack and context_stack[-1][0] == "translate":
            continue

        # Blok başlangıçları
        if stripped.startswith("label "):
            label_name = stripped.split()[1].split(":")[0]
            context_stack.append((f"label:{label_name}", indent))
            continue
        if stripped.startswith("screen "):
            screen_name = stripped.split()[1].split(":")[0]
            context_stack.append((f"screen:{screen_name}", indent))
        if stripped.startswith("menu"):
            context_stack.append(("menu", indent))
        if stripped.startswith("python") or stripped.startswith("init python") or stripped.startswith("$"):
            context_stack.append(("python", indent))
        
        # NEW v2.4.1: NVL mode context
        if stripped.startswith("nvl"):
            context_stack.append(("nvl", indent))
        
        # NEW v2.4.1: Window/frame context for better UI classification
        if stripped.startswith(("window", "frame", "vbox", "hbox")):
            block_type = stripped.split()[0].split(":")[0]
            context_stack.append((f"ui:{block_type}", indent))

        # Triple quote açılışı
        m_triple = triple_start_re.match(stripped)
        if m_triple:
            triple_buffer = (m_triple.group("delim"), idx, m_triple.group("body"))
            continue

        # Menü seçenekleri
        m_menu = menu_choice_re.match(stripped)
        if m_menu:
            q = m_menu.group("quote")
            protected, ph = protect_placeholders(q[1:-1])
            q_raw = m_menu.group("quote")
            entries.append(
                {
                    "text": restore_placeholders(protected, ph),
                    "raw_text": q_raw,
                    "line_number": idx + 1,
                    "context_line": line,
                    "text_type": "menu",
                    "file_path": file_path,
                    "context_path": current_context_path(),
                }
            )
            continue

        # Screen elemanları
        if context_stack and context_stack[-1][0].startswith("screen"):
            for sm in screen_elem_re.finditer(stripped):
                q = sm.group("quote")
                protected, ph = protect_placeholders(q[1:-1])
                q_raw = sm.group("quote")
                entries.append(
                    {
                        "text": restore_placeholders(protected, ph),
                        "raw_text": q_raw,
                        "line_number": idx + 1,
                        "context_line": line,
                        "text_type": sm.group(1),
                        "file_path": file_path,
                        "context_path": current_context_path(),
                    }
                )

        # Python _() çağrıları
        if context_stack and context_stack[-1][0] == "python":
            m_py = python_call_re.search(stripped)
            if m_py:
                q = m_py.group("quote")
                protected, ph = protect_placeholders(q[1:-1])
                q_raw = m_py.group("quote")
                entries.append(
                    {
                        "text": restore_placeholders(protected, ph),
                        "raw_text": q_raw,
                        "line_number": idx + 1,
                        "context_line": line,
                        "text_type": "python_translatable",
                        "file_path": file_path,
                        "context_path": current_context_path(),
                    }
                )
                continue
            # renpy.say/notify içindeki metinler
            m_notify = notify_call_re.search(stripped)
            if m_notify:
                q = m_notify.group("quote")
                protected, ph = protect_placeholders(q[1:-1])
                q_raw = m_notify.group("quote")
                entries.append(
                    {
                        "text": restore_placeholders(protected, ph),
                        "raw_text": q_raw,
                        "line_number": idx + 1,
                        "context_line": line,
                        "text_type": "python_notify",
                        "file_path": file_path,
                        "context_path": current_context_path(),
                    }
                )
                continue
            # renpy.input varsayılan metin
            m_input = input_call_re.search(stripped)
            if m_input:
                q = m_input.group("quote")
                protected, ph = protect_placeholders(q[1:-1])
                q_raw = m_input.group("quote")
                entries.append(
                    {
                        "text": restore_placeholders(protected, ph),
                        "raw_text": q_raw,
                        "line_number": idx + 1,
                        "context_line": line,
                        "text_type": "python_input",
                        "file_path": file_path,
                        "context_path": current_context_path(),
                    }
                )
                continue
            # Text("...") displayable
            m_text_disp = text_displayable_re.search(stripped)
            if m_text_disp:
                q = m_text_disp.group("quote")
                protected, ph = protect_placeholders(q[1:-1])
                q_raw = m_text_disp.group("quote")
                entries.append(
                    {
                        "text": restore_placeholders(protected, ph),
                        "raw_text": q_raw,
                        "line_number": idx + 1,
                        "context_line": line,
                        "text_type": "text_displayable",
                        "file_path": file_path,
                        "context_path": current_context_path(),
                    }
                )
                continue
            continue

        # Karakterli diyalog
        m_dialog = dialog_re.match(stripped)
        if m_dialog:
            q = m_dialog.group("quote")
            protected, ph = protect_placeholders(q[1:-1])
            q_raw = m_dialog.group("quote")
            entries.append(
                {
                    "text": restore_placeholders(protected, ph),
                    "raw_text": q_raw,
                    "line_number": idx + 1,
                    "context_line": line,
                    "text_type": "dialogue",
                    "character": m_dialog.group("char"),
                    "file_path": file_path,
                    "context_path": current_context_path(),
                }
            )
            continue

        # Narrator
        m_narr = narrator_re.match(stripped)
        if m_narr:
            q = m_narr.group("quote")
            protected, ph = protect_placeholders(q[1:-1])
            q_raw = m_narr.group("quote")
            entries.append(
                {
                    "text": restore_placeholders(protected, ph),
                    "raw_text": q_raw,
                    "line_number": idx + 1,
                    "context_line": line,
                    "text_type": "narration",
                    "file_path": file_path,
                    "context_path": current_context_path(),
                }
            )
            continue

    return entries
