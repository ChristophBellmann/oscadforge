
#!/bin/bash

CONFIG_FILE="config/export-to-stl.yaml"
OUTPUT_BASE_DIR="out"

# Entspricht: 

# python3 -m oscadforge.oscadforge oscadforge/templates/model_opengrid-papierkorb-1_full.yaml oscadforge/config/export-to-stl.yaml && \
# python3 -m oscadforge.oscadforge oscadforge/templates/model_opengrid-papierkorb-1_lite.yaml oscadforge/config/export-to-stl.yaml && \
# python3 -m oscadforge.oscadforge oscadforge/templates/model_opengrid-papierkorb-2_full.yaml oscadforge/config/export-to-stl.yaml && \
# python3 -m oscadforge.oscadforge oscadforge/templates/model_opengrid-papierkorb-2_lite.yaml oscadforge/config/export-to-stl.yaml

# aber incl Berechnung der Maße mit admesh
# braucht `sudo apt install admesh

# Die vier Aufrufe passieren gleichzeitig, die Berechnung der Maße wenn Daten fertig.

# Liste der zu verarbeitenden Modelle. 
# WICHTIG: Diese Namen MÜSSEN zu den Ordnern passen, die oscadforge in 'out/' erstellt.
MODELS=(
    opengrid-papierkorb-1_full
    opengrid-papierkorb-1_lite
    opengrid-papierkorb-2_full
    opengrid-papierkorb-2_lite
)

echo "--- Starte Generierung (Parallel) und Dimensionsanalyse ---"

PIDS=() # Array, um die Prozess-IDs (PIDs) zu speichern

for model_name in "${MODELS[@]}"; do
    # Der Template-Dateiname hat das "model_" Präfix, die Ausgabe nicht.
    TEMPLATE_FILE="templates/model_${model_name}.yaml"
    
    echo "Starte Generierung von ${model_name} im Hintergrund mit Template ${TEMPLATE_FILE}..."
    
    # Führe den oscadforge Befehl aus und schicke ihn mit '&' in den Hintergrund
    # Wir übergeben den vollen Pfad zum Template und zur Config
    python3 -m oscadforge "$TEMPLATE_FILE" "$CONFIG_FILE" &
    
    # Speichere die PID (Process ID) des zuletzt gestarteten Hintergrundprozesses
    PIDS+=($!)
done

echo "Alle Generierungsprozesse laufen. Warte auf Abschluss..."

# Warte auf alle Hintergrundprozesse, die wir gestartet haben
wait "${PIDS[@]}"

echo "Alle Generierungsprozesse abgeschlossen. Starte Dimensionsanalyse..."

# --- Phase 2: Dimensionsanalyse der fertigen STL-Dateien (Seriell) ---

for model_name in "${MODELS[@]}"; do
    
    # Der Pfad zur STL und Summary verwendet den bereinigten model_name
    STL_FILE="./../${OUTPUT_BASE_DIR}/${model_name}/${model_name}.stl"
    SUMMARY_FILE="./../${OUTPUT_BASE_DIR}/${model_name}/summary.md"


    if [ -f "$STL_FILE" ]; then
        echo "Analysiere Dimensionen für $STL_FILE..."

        ADMESH_OUTPUT=$(admesh "$STL_FILE" 2>&1)

        # parsen: Die gesamte Größen-Sektion extrahieren
        # grep sucht nach der Zeile mit 'Min X' und extrahiert den Wert
        MIN_X=$(echo "$ADMESH_OUTPUT" | grep 'Min X =' | awk -F'[,=]' '{print $2}' | tr -d ' ')
        MAX_X=$(echo "$ADMESH_OUTPUT" | grep 'Min X =' | awk -F'[,=]' '{print $4}' | tr -d ' ')
        MIN_Y=$(echo "$ADMESH_OUTPUT" | grep 'Min Y =' | awk -F'[,=]' '{print $2}' | tr -d ' ')
        MAX_Y=$(echo "$ADMESH_OUTPUT" | grep 'Min Y =' | awk -F'[,=]' '{print $4}' | tr -d ' ')
        MIN_Z=$(echo "$ADMESH_OUTPUT" | grep 'Min Z =' | awk -F'[,=]' '{print $2}' | tr -d ' ')
        MAX_Z=$(echo "$ADMESH_OUTPUT" | grep 'Min Z =' | awk -F'[,=]' '{print $4}' | tr -d ' ')

        # Berechnung der tatsächlichen Länge, Breite, Höhe mit 'bc'

	LENGTH=$(echo "scale=0; ($MAX_X - $MIN_X) / 1" | bc)
	WIDTH=$(echo "scale=0; ($MAX_Y - $MIN_Y) / 1" | bc)
	HEIGHT=$(echo "scale=0; ($MAX_Z - $MIN_Z) / 1" | bc)
	
        # scale=2 wären 2 nachkommastellen, hier scale=0 aber .000000 sind da, daher:
	# Die Division durch 1 schneitet das Ergebnis korrekt abschneidet.
	# Alternativ %.* bedeutet: Entferne alles, was nach dem letzten Punkt kommt.
	# Also echo "Länge:  ${LENGTH%.*} mm" >> "$SUMMARY_FILE"
      
        #  Ausgabe in die summary.md Datei
        echo "# Zusammenfassung der Modelldimensionen" > "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
        echo "## Dateiname: ${model_name}.stl" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
        echo "### Bounding Box Koordinaten:" >> "$SUMMARY_FILE"
        echo "Länge:  ${LENGTH%.*} mm" >> "$SUMMARY_FILE"
        echo "Breite: ${WIDTH%.*} mm" >> "$SUMMARY_FILE"
        echo "Höhe:   ${HEIGHT%.*} mm" >> "$SUMMARY_FILE"
        
        echo "Zusammenfassung in $SUMMARY_FILE gespeichert."
    else
        echo "FEHLER: STL-Datei $STL_FILE wurde nicht gefunden. Überprüfen Sie die oscadforge-Ausgabe."
    fi
    
    echo "---"
done

echo "--- Prozess abgeschlossen ---"

