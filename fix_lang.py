import os
import sys
import subprocess

# --- 1. The Spanish Translation Content ---
PO_CONTENT = r"""
msgid ""
msgstr ""
"Project-Id-Version: Leer Mexico 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"

# --- Common Buttons & Labels ---
msgid "Back"
msgstr "Atrás"

msgid "Back to Dashboard"
msgstr "Volver al Panel"

msgid "Home"
msgstr "Inicio"

msgid "Loading..."
msgstr "Cargando..."

msgid "Date"
msgstr "Fecha"

msgid "Activity"
msgstr "Actividad"

msgid "Points"
msgstr "Puntos"

msgid "Description"
msgstr "Descripción"

msgid "Edit"
msgstr "Editar"

msgid "Delete"
msgstr "Eliminar"

msgid "Cancel"
msgstr "Cancelar"

msgid "Clear"
msgstr "Limpiar"

msgid "Save"
msgstr "Guardar"

msgid "Status"
msgstr "Estado"

msgid "Active"
msgstr "Activo"

msgid "Inactive"
msgstr "Inactivo"

msgid "View"
msgstr "Ver"

msgid "Login"
msgstr "Iniciar Sesión"

# --- Dashboard (index.html) ---
msgid "Dashboard"
msgstr "Panel de Control"

msgid "Student Actions"
msgstr "Acciones de Alumno"

msgid "Reward Points (Activity)"
msgstr "Otorgar Puntos (Actividad)"

msgid "Redeem Points (Prizes)"
msgstr "Canjear Puntos (Premios)"

msgid "Student Directory"
msgstr "Directorio de Alumnos"

msgid "Add New Student"
msgstr "Agregar Nuevo Alumno"

msgid "Management"
msgstr "Administración"

msgid "Prize Inventory"
msgstr "Inventario de Premios"

msgid "Activity Catalog"
msgstr "Catálogo de Actividades"

msgid "System Status"
msgstr "Estado del Sistema"

msgid "App Logs"
msgstr "Registros (Logs)"

msgid "System Audit Logs"
msgstr "Auditoría del Sistema"

# --- Student Profile (student_profile.html) ---
msgid "Profile"
msgstr "Perfil"

msgid "Balance"
msgstr "Saldo"

msgid "Contact & Student Info"
msgstr "Contacto e Info del Alumno"

msgid "Quick Actions"
msgstr "Acciones Rápidas"

msgid "Reward Points"
msgstr "Otorgar Puntos"

msgid "Redeem Points"
msgstr "Canjear Puntos"

msgid "Activity History"
msgstr "Historial de Actividades"

msgid "Export CSV"
msgstr "Exportar CSV"

msgid "FILTER:"
msgstr "FILTRO:"

msgid "All Time"
msgstr "Todo el Tiempo"

msgid "Last 7 Days"
msgstr "Últimos 7 Días"

msgid "Last 30 Days"
msgstr "Últimos 30 Días"

msgid "Last 90 Days"
msgstr "Últimos 90 Días"

msgid "Loading history..."
msgstr "Cargando historial..."

msgid "No transactions found for the selected range."
msgstr "No se encontraron transacciones en este rango."

msgid "Grade"
msgstr "Grado"

msgid "Class"
msgstr "Clase"

# --- Record Activity (record_activity.html) ---
msgid "Student Search"
msgstr "Buscar Alumno"

msgid "Search by name or ID..."
msgstr "Buscar por nombre o ID..."

msgid "Search results will appear here"
msgstr "Los resultados aparecerán aquí"

msgid "-- Select Activity --"
msgstr "-- Seleccionar Actividad --"

msgid "Points Override"
msgstr "Ajuste Manual de Puntos"

msgid "Optional notes..."
msgstr "Notas opcionales..."

msgid "Post Transaction"
msgstr "Registrar Transacción"

msgid "Recent Transactions"
msgstr "Transacciones Recientes"

msgid "Select a student to view their history"
msgstr "Selecciona un alumno para ver su historial"

msgid "No transactions found."
msgstr "No se encontraron transacciones."

# --- Add Student (add_student.html) ---
msgid "Add Student"
msgstr "Agregar Alumno"

msgid "Add Student — Leer México"
msgstr "Agregar Alumno — Leer México"

msgid "Full Name"
msgstr "Nombre Completo"

msgid "Full name as it appears on certificates"
msgstr "Nombre tal como aparece en actas"

msgid "Nickname"
msgstr "Apodo"

msgid "Optional display name"
msgstr "Nombre corto opcional"

msgid "Parent / Guardian name (optional)"
msgstr "Nombre del Padre/Tutor (opcional)"

msgid "Parent or guardian name"
msgstr "Nombre del padre o tutor"

msgid "Email (optional)"
msgstr "Correo (opcional)"

msgid "Phone (optional)"
msgstr "Teléfono (opcional)"

msgid "Phone number in Mexico format (10-digits)."
msgstr "Número a 10 dígitos."

msgid "I agree to receive SMS messages"
msgstr "Acepto recibir mensajes SMS"

msgid "Classroom"
msgstr "Salón"

msgid "-- select --"
msgstr "-- seleccionar --"

msgid "Possible matches found"
msgstr "Posibles coincidencias encontradas"

msgid "No Class Assigned"
msgstr "Sin Salón Asignado"

msgid "Student created."
msgstr "Alumno creado exitosamente."

msgid "Full name is required."
msgstr "El nombre completo es obligatorio."

msgid "Potential duplicates returned from server"
msgstr "Posibles duplicados detectados"

msgid "Save Anyway"
msgstr "Guardar de todas formas"

# --- Prizes (prizes.html & redeem.html) ---
msgid "Prize Manager"
msgstr "Gestor de Premios"

msgid "Prize Name"
msgstr "Nombre del Premio"

msgid "Point Cost"
msgstr "Costo en Puntos"

msgid "Stock"
msgstr "Existencias"

msgid "Description (Optional)"
msgstr "Descripción (Opcional)"

msgid "Save Prize"
msgstr "Guardar Premio"

msgid "Current Inventory"
msgstr "Inventario Actual"

msgid "Search by name..."
msgstr "Buscar por nombre..."

msgid "Hide inactive items"
msgstr "Ocultar inactivos"

msgid "No matching prizes found."
msgstr "No se encontraron premios."

msgid "Redeem Prizes"
msgstr "Canjear Premios"

msgid "Identify Student"
msgstr "Identificar Alumno"

msgid "Search Name or ID..."
msgstr "Buscar Nombre o ID..."

msgid "Recent History"
msgstr "Historial Reciente"

msgid "Select a student"
msgstr "Selecciona un alumno"

msgid "Redeemable Prizes"
msgstr "Premios Disponibles"

msgid "Filter by prize name..."
msgstr "Filtrar por nombre..."

msgid "Hide unaffordable"
msgstr "Ocultar inalcanzables"

msgid "Redeem"
msgstr "Canjear"

msgid "Confirm redemption of"
msgstr "Confirmar canje de"

msgid "Pts"
msgstr "Pts"

# --- Activities (add_activity.html) ---
msgid "Manage Activities"
msgstr "Gestionar Actividades"

msgid "Activity Name"
msgstr "Nombre de Actividad"

msgid "Default Points"
msgstr "Puntos Predeterminados"

msgid "Briefly explain the criteria..."
msgstr "Explicar brevemente los criterios..."

msgid "Save Activity"
msgstr "Guardar Actividad"

msgid "Configured Activities"
msgstr "Actividades Configuradas"

msgid "No matching activities found."
msgstr "No se encontraron actividades."

msgid "Reports"
msgstr "Reportes"

msgid "Download Redemption Log"
msgstr "Descargar Bitácora de Canjes"

msgid "Download Current Inventory"
msgstr "Descargar Inventario Actual"

msgid "Are you sure you want to delete"
msgstr "¿Estás seguro de eliminar"
"""

# --- 2. Setup Directories ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANS_DIR = os.path.join(BASE_DIR, 'translations')
ES_DIR = os.path.join(TRANS_DIR, 'es', 'LC_MESSAGES')
PO_FILE = os.path.join(ES_DIR, 'messages.po')
MO_FILE = os.path.join(ES_DIR, 'messages.mo')

def run():
    print("--- FIXING TRANSLATIONS ---")
    
    # 1. Create Directories
    if not os.path.exists(ES_DIR):
        print(f"Creating directory: {ES_DIR}")
        os.makedirs(ES_DIR)

    # 2. Write the .po file
    print(f"Writing fresh translation keys to: {PO_FILE}")
    with open(PO_FILE, 'w', encoding='utf-8') as f:
        f.write(PO_CONTENT)

    # 3. Compile to .mo
    print("Compiling .po to .mo binary...")
    
    # Method A: Try using pybabel command line (Standard)
    try:
        subprocess.run(['pybabel', 'compile', '-d', 'translations'], check=True)
        print("SUCCESS: Compiled using 'pybabel' command.")
    except Exception:
        print("WARNING: 'pybabel' command failed or not found. Trying Python internal compile...")
        
        # Method B: Python internal compile (Backup if CLI fails)
        try:
            from babel.messages.frontend import compile_catalog
            from babel.messages.catalog import Catalog
            from babel.messages.pofile import read_po
            from babel.messages.mofile import write_mo
            
            with open(PO_FILE, 'r', encoding='utf-8') as f:
                catalog = read_po(f)
            
            with open(MO_FILE, 'wb') as f:
                write_mo(f, catalog)
                
            print(f"SUCCESS: Compiled internally to {MO_FILE}")
        except ImportError:
            print("CRITICAL ERROR: Could not compile. Please ensure 'Babel' is installed (pip install Babel).")
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    run()