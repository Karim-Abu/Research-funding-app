"""Gemeinsame Schema-Form für provider-native Structured Outputs.

Beide Provider verlangen für strikte Structured Outputs dieselbe Grundform
(OpenAI Responses ``text.format.json_schema`` mit ``strict: true``; Anthropic
Messages ``output_config.format`` mit ``type: json_schema``): jedes Objekt trägt
``additionalProperties: false`` und listet alle Properties in ``required``; das
Keyword ``default`` wird nicht unterstützt.

Die Transformation ist deterministisch und für unsere pydantic-Modelle
verlustfrei: optionale Felder bleiben als ``anyOf: [T, null]`` ausdrückbar,
Listen-Defaults werden schlicht als ``[]`` gesendet. Sie ist **kein**
Validierungsschritt — die pydantic-Prüfung im Gateway bleibt die einzige
Autorität darüber, was akzeptiert wird.
"""
from __future__ import annotations

# Keywords, die beide Structured-Output-Implementierungen ablehnen (Anthropic
# dokumentiert sie explizit als «not supported»). Wir senden sie nicht — die
# fachliche Grenze bleibt in pydantic bestehen und wird dort geprüft.
UNSUPPORTED_KEYWORDS = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "minItems", "maxItems", "uniqueItems",
    "minProperties", "maxProperties", "patternProperties", "propertyNames",
})


def strict_schema(schema: dict) -> dict:
    """Pydantic JSON Schema → strikte Structured-Outputs-Form.

    Deterministisch (spiegelt ``to_strict_json_schema`` des OpenAI-SDK): jedes
    Objekt bekommt ``additionalProperties: false`` und ALLE Properties als
    ``required``; ``default`` wird entfernt.
    """

    def walk(node: object) -> object:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out: dict = {}
        for key, value in node.items():
            if key == "default":  # Schema-Keyword, im strict-Modus unzulässig
                continue
            if key in ("properties", "$defs"):
                # Schlüssel sind Property-/Definitionsnamen, Werte sind Schemata
                out[key] = {name: walk(sub) for name, sub in value.items()}
            else:
                out[key] = walk(value)
        if "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out

    return walk(schema)  # type: ignore[return-value]


def unsupported_keywords_in(schema: dict) -> set[str]:
    """Nicht unterstützte Schema-Keywords (leer = provider-tauglich).

    Guard für die Structured-Output-Pfade: ein Schema mit solchen Keywords
    würde einen 4xx auslösen — das fällt so vor dem Call auf, nicht im Live-Lauf.
    """
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in UNSUPPORTED_KEYWORDS:
                found.add(key)
            if key in ("properties", "$defs"):
                for sub in value.values():
                    walk(sub)
            else:
                walk(value)

    walk(schema)
    return found
