import os
import sys

# 1. DEFINE PATHS
basedir = os.path.abspath(os.path.dirname(__file__))
translations_dir = os.path.join(basedir, 'translations')
es_dir = os.path.join(translations_dir, 'es', 'LC_MESSAGES')
po_file = os.path.join(es_dir, 'messages.po')
mo_file = os.path.join(es_dir, 'messages.mo')

# 2. ENSURE DIRECTORIES EXIST
os.makedirs(es_dir, exist_ok=True)

# 3. DEFINE TRANSLATIONS
PO_HEADER = r"""
msgid ""
msgstr ""
"Project-Id-Version: 1.0\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 00:00+0000\n"
"PO-Revision-Date: 2024-01-01 00:00+0000\n"
"Last-Translator: \n"
"Language-Team: \n"
"Language: es\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"""

TRANSLATIONS = {
    # --- NAVIGATION & GENERAL ---
    "Dashboard": "Panel de Control",
    "Student Actions": "Acciones de Estudiantes",
    "Management": "Administración",
    "System Status": "Estado del Sistema",
    "Help": "Ayuda",
    "Back to Dashboard": "Volver al Panel",
    "Back": "Atrás",
    "Search": "Buscar",
    "Reset": "Reiniciar",
    
    # --- BUTTONS ---
    "Reward Points (Activity)": "Otorgar Puntos (Actividad)",
    "Redeem Points (Prizes)": "Canjear Puntos (Premios)",
    "Student Directory": "Directorio de Estudiantes",
    "Add New Student": "Agregar Nuevo Estudiante",
    "Prize Inventory": "Inventario de Premios",
    "Activity Catalog": "Catálogo de Actividades",
    "App Logs": "Registros de la App",
    "System Audit Logs": "Auditoría del Sistema",
    "Reports": "Reportes",
    "View Redemption Log": "Ver Bitácora de Canjes",
    "View Inventory Report": "Ver Reporte de Inventario",
    "Download CSV": "Descargar CSV",

    # --- HELP & DOCUMENTATION ---
    "Help & Documentation": "Ayuda y Documentación",
    "Staff Support Center": "Centro de Soporte al Personal",
    "Print Guide": "Imprimir Guía",
    "Cheat Sheet": "Hoja de Referencia",
    "User Manual": "Manual de Usuario",
    "FAQ": "Preguntas Frecuentes",
    
    # Cheat Sheet Specifics (Updated)
    "Top 3 Daily Actions": "Top 3 Acciones Diarias",
    "Reward Points (Record Activity)": "Otorgar Puntos (Registrar Actividad)",
    "Go to": "Ir a",
    "Click": "Hacer clic en",
    "Step 1: Search for the student (Type name → Select from list).": "Paso 1: Busque al estudiante (Escriba nombre → Seleccione de la lista).",
    "Step 2: Select the Activity from the dropdown.": "Paso 2: Seleccione la Actividad del menú.",
    "Step 3: (Optional) Add a note or adjust points.": "Paso 3: (Opcional) Agregue una nota o ajuste puntos.",
    "Step 4: Click \"Post Transaction\".": "Paso 4: Haga clic en \"Registrar Transacción\".",
    "Success": "Éxito",
    "The student's new balance appears immediately at the top.": "El nuevo saldo aparece inmediatamente arriba.",
    
    "Redeem a Prize": "Canjear un Premio",
    "Step 1: Search for the student.": "Paso 1: Busque al estudiante.",
    "Step 2: Check their Balance (displayed in big blue numbers).": "Paso 2: Verifique su Saldo (números azules grandes).",
    "Step 3: Find the prize in the list below.": "Paso 3: Encuentre el premio en la lista de abajo.",
    "Grayed out?": "¿Aparece gris?",
    "They don't have enough points.": "No tienen suficientes puntos.",
    "Step 4: Click the \"Redeem\" button next to the prize.": "Paso 4: Haga clic en el botón \"Canjear\" junto al premio.",

    "Required": "Obligatorio",
    "Full Name, Classroom, Grade.": "Nombre Completo, Salón, Grado.",
    "Note:": "Nota:",
    "Always search the directory first to make sure they don't already exist!": "¡Siempre busque en el directorio primero para asegurarse de que no existen!",

    # Troubleshooting Section (New)
    "Troubleshooting Quick Tips": "Tips Rápidos de Solución de Problemas",
    "I made a mistake giving points!": "¡Me equivoqué dando puntos!",
    "Go to Reward Points. Select the student. Choose \"Manual Adjustment\" (or similar) and enter a": "Vaya a Otorgar Puntos. Seleccione al estudiante. Elija \"Ajuste Manual\" e ingrese un",
    "negative number": "número negativo",
    "to remove the points.": "para quitar los puntos.",
    
    "I can't find a student.": "No encuentro a un estudiante.",
    "Try searching by just their First Name or ID number.": "Intente buscar solo por su primer nombre o número de ID.",
    
    "The system is stuck.": "El sistema está trabado.",
    "Refresh the page (F5 or Ctrl+R).": "Refresque la página (F5 o Ctrl+R).",

    # Manual Section
    "Managing Students": "Gestión de Estudiantes",
    "Adding a New Student": "Agregar Nuevo Estudiante",
    "Navigate to \"Add New Student\". Enter their Full Name, Grade, and Classroom. Always check the directory first to ensure they do not already exist.": "Vaya a \"Agregar Nuevo Estudiante\". Ingrese Nombre Completo, Grado y Salón. ¡Siempre verifique el directorio primero para asegurarse de que no existan!",
    
    "Viewing History": "Ver Historial",
    "Go to the Student Directory, search for a student, and click \"View Profile\". You can see their last 10 transactions and download their full history.": "Vaya al Directorio, busque al estudiante y haga clic en \"Ver Perfil\". Puede ver sus últimas 10 transacciones y descargar el historial completo.",
    
    "Managing Inventory": "Gestión de Inventario",
    "Adding/Updating Prizes": "Agregar/Actualizar Premios",
    "Go to \"Prize Inventory\". To add a new prize, use the form at the top. To update stock for an existing prize, find it in the list below and click \"Edit\".": "Vaya a \"Inventario de Premios\". Para agregar uno nuevo, use el formulario superior. Para actualizar existencias, busque el premio abajo y haga clic en \"Editar\".",
    
    "Access reports from the Dashboard. You can view them on-screen or download CSV files for Excel.": "Acceda a los reportes desde el Panel. Puede verlos en pantalla o descargar archivos CSV para Excel.",
    "Redemption Log:": "Bitácora de Canjes:",
    "See who bought what and when.": "Vea quién canjeó qué y cuándo.",
    "Inventory Report:": "Reporte de Inventario:",
    "See current stock levels for stocktaking.": "Vea los niveles actuales para el conteo de existencias.",

    # FAQ Section
    "Frequently Asked Questions": "Preguntas Frecuentes",
    "I entered the wrong points! How do I undo it?": "¡Ingresé los puntos incorrectos! ¿Cómo lo deshago?",
    "Go to \"Reward Points\", select the student, and post a transaction with a **negative** point value (e.g., -50) to reverse the error.": "Vaya a \"Otorgar Puntos\", seleccione al estudiante y registre una transacción con valor **negativo** (ej. -50) para revertir el error.",
    
    "Why is the Redeem button grayed out?": "¿Por qué el botón Canjear está gris?",
    "Either the student does not have enough points, OR the item is out of stock.": "El estudiante no tiene suficientes puntos O el artículo está agotado.",
    
    "Can I delete a student?": "¿Puedo eliminar a un estudiante?",
    "No. We do not delete students to preserve historical data. Please ask an administrator to mark them as inactive.": "No. No eliminamos estudiantes para preservar los datos históricos. Pida a un administrador que los marque como inactivos.",
    
    "The Spanish translation is missing?": "¿Falta la traducción al español?",
    "Refresh the page. If it persists, click \"ES\" in the top right corner.": "Refresque la página. Si persiste, haga clic en \"ES\" en la esquina superior derecha."
}

# 4. WRITE PO FILE
print(f"Generating {po_file}...")
with open(po_file, 'w', encoding='utf-8') as f:
    f.write(PO_HEADER)
    for k, v in TRANSLATIONS.items():
        # Escape quotes just in case
        k_esc = k.replace('"', '\\"')
        v_esc = v.replace('"', '\\"')
        f.write(f'\nmsgid "{k_esc}"\n')
        f.write(f'msgstr "{v_esc}"\n')

# 5. COMPILE TO MO FILE
try:
    from babel.messages.pofile import read_po
    from babel.messages.mofile import write_mo
    
    print(f"Compiling to {mo_file}...")
    with open(po_file, 'rb') as f:
        catalog = read_po(f)
    
    with open(mo_file, 'wb') as f:
        write_mo(f, catalog)
        
    print("SUCCESS: Translations updated!")

except ImportError:
    print("ERROR: 'Babel' library not found.")
    print("Please run this command manually:")
    print("pip install Babel")