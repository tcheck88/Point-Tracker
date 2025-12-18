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
    # --- GLOBAL & NAVIGATION ---
    "Main": "Principal",
    "Actions": "Acciones",
    "Dashboard": "Panel de Control",
    "Back to Dashboard": "Volver al Panel",
    "Back": "Atrás",
    "Home": "Inicio",
    "Search": "Buscar",
    "Reset": "Reiniciar",
    "Cancel": "Cancelar",
    "View": "Ver",
    "Save": "Guardar",
    "Login": "Iniciar Sesión",
    "Logout": "Cerrar Sesión",
    "Help Center": "Centro de Ayuda",
    "Settings": "Configuración",
    "Admin Zone": "Zona de Admin",
    
    # --- INDEX / MENU ---
    "Student Actions": "Acciones de Estudiantes",
    "Reward Points (Activity)": "Otorgar Puntos (Actividad)",
    "Redeem Points (Prizes)": "Canjear Puntos (Premios)",
    "Student Directory": "Directorio de Estudiantes",
    "Add New Student": "Agregar Nuevo Estudiante",
    "Management": "Administración",
    "Prize Inventory": "Inventario de Premios",
    "Activity Catalog": "Catálogo de Actividades",
    "Reports": "Reportes",
    "View Redemption Log": "Ver Bitácora de Canjes",
    "View Inventory Report": "Ver Reporte de Inventario",
    "System Status": "Estado del Sistema",
    "App Logs": "Registros de la App",
    "System Audit Logs": "Auditoría del Sistema",

    # --- STUDENT DIRECTORY & HISTORY ---
    "Back to Students": "Volver a Estudiantes",
    "Search by name, nickname, or ID...": "Buscar por nombre, apodo o ID...",
    "Search Results": "Resultados de Búsqueda",
    "Hide zero points": "Ocultar cero puntos",
    "Searching...": "Buscando...",
    "No matching students found.": "No se encontraron estudiantes.",
    "Error connecting to server.": "Error al conectar con el servidor.",
    "Activity History": "Historial de Actividad",
    "Date/Time": "Fecha/Hora",
    "Recorded By": "Registrado Por",
    "Trans. ID": "ID Trans.",
    "Download CSV": "Descargar CSV",

    # --- ADD / EDIT STUDENT ---
    "Add Student": "Agregar Alumno",
    "Add Student — Leer México": "Agregar Alumno — Leer México",
    "Edit Student": "Editar Estudiante",
    "Back to Profile": "Volver al Perfil",
    "Edit Student Details": "Editar Datos del Estudiante",
    "Update the information below.": "Actualice la información a continuación.",
    "Save Changes": "Guardar Cambios",
    "Failed to update student.": "Error al actualizar estudiante.",
    "Full Name": "Nombre Completo",
    "Full name as it appears on certificates": "Nombre completo como aparece en certificados",
    "Nickname": "Apodo",
    "Optional display name": "Nombre opcional para mostrar",
    "Parent / Guardian name (optional)": "Nombre del Padre / Tutor (opcional)",
    "Parent or guardian name": "Nombre del padre o tutor",
    "Email (optional)": "Correo electrónico (opcional)",
    "Phone (optional)": "Teléfono (opcional)",
    "Phone number in Mexico format (10-digits).": "Número a 10 dígitos.",
    "I agree to receive SMS messages": "Acepto recibir mensajes SMS",
    "Classroom": "Salón",
    "Classroom / Homeroom": "Salón / Aula",
    "Grade": "Grado",
    "Grade Level": "Grado Escolar",
    "Select Grade": "Seleccionar Grado",
    "-- select --": "-- seleccionar --",
    "Possible matches found": "Posibles coincidencias encontradas",
    "No Class Assigned": "Sin Salón Asignado",
    "Full name is required.": "El nombre completo es obligatorio.",
    "Student created.": "Estudiante creado.",
    "Potential duplicates returned from server": "Posibles duplicados detectados",
    "Save Anyway": "Guardar de todos modos",
    "Network or server error.": "Error de red o servidor.",
    "Parent / Contact Info": "Info de Padre / Contacto",
    "Parent Name": "Nombre del Padre",
    "Phone Number": "Número de Teléfono",
    "Email Address": "Correo Electrónico",

    # --- STUDENT PROFILE ---
    "Profile": "Perfil",
    "Edit Details": "Editar Datos",
    "Balance": "Saldo",
    "Contact & Student Info": "Información de Contacto",
    "Quick Actions": "Acciones Rápidas",
    "Export CSV": "Exportar CSV",
    "FILTER:": "FILTRO:",
    "All Time": "Todos los Tiempos",
    "Last 7 Days": "Últimos 7 Días",
    "Last 30 Days": "Últimos 30 Días",
    "Last 90 Days": "Últimos 90 Días",
    "Date": "Fecha",
    "Activity": "Actividad",
    "Points": "Puntos",
    "Loading history...": "Cargando historial...",
    "Loading...": "Cargando...",
    "Class": "Clase",
    "No transactions found for the selected range.": "No se encontraron transacciones para el rango seleccionado.",

    # --- REWARD POINTS (RECORD ACTIVITY) ---
    "Reward Points": "Otorgar Puntos",
    "Student Search": "Buscar Estudiante",
    "Search by name or ID...": "Buscar por nombre o ID...",
    "Search results will appear here": "Los resultados aparecerán aquí",
    "-- Select Activity --": "-- Seleccionar Actividad --",
    "Points Override": "Anular Puntos",
    "Description": "Descripción",
    "Optional notes...": "Notas opcionales...",
    "Post Transaction": "Registrar Transacción",
    "Recent Transactions": "Transacciones Recientes",
    "Select a student to view their history": "Seleccione un estudiante para ver su historial",
    "No transactions found.": "No se encontraron transacciones.",

    # --- REDEEM PRIZES ---
    "Redeem Prizes": "Canjear Premios",
    "Identify Student": "Identificar Estudiante",
    "Search Name or ID...": "Buscar Nombre o ID...",
    "Recent History": "Historial Reciente",
    "Pts": "Pts",
    "Select a student": "Seleccione un estudiante",
    "Redeemable Prizes": "Premios Canjeables",
    "Filter by prize name...": "Filtrar por nombre...",
    "Hide unaffordable": "Ocultar inasequibles",
    "Redeem": "Canjear",
    "Not enough points or out of stock": "Puntos insuficientes o agotado",
    "Confirm redemption of": "Confirmar canje de",

    # --- PRIZE MANAGER (NEW) ---
    "Prize Manager": "Gestor de Premios",
    "Prize Name": "Nombre del Premio",
    "Point Cost": "Costo en Puntos",
    "Stock": "Existencia",
    "Stock:": "Existencia:",
    "Save Prize": "Guardar Premio",
    "Current Inventory": "Inventario Actual",
    "Search by name...": "Buscar por nombre...",
    "Hide inactive items": "Ocultar inactivos",
    "No matching prizes found.": "No se encontraron premios.",
    "Edit": "Editar",
    "Delete": "Eliminar",
    "Are you sure you want to delete": "¿Está seguro que desea eliminar",

    # --- ACTIVITY MANAGER ---
    "Activity Manager": "Gestor de Actividades",
    "Activity Name": "Nombre de la Actividad",
    "Default Points": "Puntos Predeterminados",
    "Status": "Estado",
    "Active": "Activo",
    "Inactive": "Inactivo",
    "Description (Optional)": "Descripción (Opcional)",
    "Briefly explain the criteria...": "Explique brevemente los criterios...",
    "Save Activity": "Guardar Actividad",
    "Clear": "Limpiar",
    "Configured Activities": "Actividades Configuradas",
    "No matching activities found.": "No se encontraron actividades.",

    # --- REPORTS & LOGS ---
    "Redemption Report": "Reporte de Canjes",
    "Redemption Log": "Bitácora de Canjes",
    "Stock Report": "Reporte de Existencias",
    "Inventory Report": "Reporte de Inventario",
    "Prize": "Premio",
    "Staff": "Personal",
    "Today": "Hoy",
    "Student": "Estudiante",
    "Cost": "Costo",
    "No redemptions found for this period.": "No se encontraron canjes para este periodo.",
    "No prizes found.": "No se encontraron premios.",
    
    # -- SYSTEM LOGS (NEW) --
    "System Logs - Leer México": "Registros del Sistema - Leer México",
    "Refresh": "Actualizar",
    "Download Full Log": "Descargar Log Completo",
    "Clear Logs": "Limpiar Logs",
    "Loading system logs...": "Cargando registros del sistema...",
    "No logs found.": "No se encontraron registros.",
    "Error loading logs: ": "Error cargando logs: ",
    "Are you sure? This will archive the current log file and start a fresh one.": "¿Seguro? Esto archivará el log actual y creará uno nuevo.",
    "Logs cleared!": "¡Logs limpiados!",
    "Error: ": "Error: ",
    "Network error: ": "Error de red: ",

    # -- AUDIT LOGS (NEW) --
    "Timestamp": "Marca de tiempo",
    "Action": "Acción",
    "Details": "Detalles",
    "Staff User": "Usuario del Personal",

    # --- HELP & DOCS ---
    "Help & Documentation": "Ayuda y Documentación",
    "Staff Support Center": "Centro de Soporte al Personal",
    "Print Guide": "Imprimir Guía",
    "Cheat Sheet": "Hoja de Referencia",
    "User Manual": "Manual de Usuario",
    "FAQ": "Preguntas Frecuentes",
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
    "Add a New Student": "Agregar un Nuevo Estudiante",
    "Required": "Obligatorio",
    "Full Name.": "Nombre Completo.",
    "The Full Name will be used to search for the student so it needs to accurate and unique.": "El Nombre Completo se usará para buscar al estudiante, por lo que debe ser exacto y único.",
    "Note:": "Nota:",
    "Always search the directory first to make sure they don't already exist!": "¡Siempre busque en el directorio primero para asegurarse de que no existen!",
    "Troubleshooting Quick Tips": "Tips Rápidos de Solución de Problemas",
    "I made a mistake giving points!": "¡Me equivoqué dando puntos!",
    "negative number": "número negativo",
    "to remove the points.": "para quitar los puntos.",
    "I can't find a student.": "No encuentro a un estudiante.",
    "Use the Student Directory to see a list of students with similar names in case there is a spelling mistake.": "Use el Directorio de Estudiantes para ver una lista de nombres similares en caso de errores de ortografía.",
    "I made a mistake on student name.": "Me equivoqué en el nombre del estudiante.",
    "Use the Student Directory to find the student. Click on the student and then use the Edit Details button to update their name.": "Busque al estudiante en el Directorio. Haga clic en él y use el botón Editar Datos para corregir su nombre.",
    "The system is stuck.": "El sistema está trabado.",
    "Refresh the page (F5 or Ctrl+R).": "Refresque la página (F5 o Ctrl+R).",
    "Managing Students": "Gestión de Estudiantes",
    "Adding a New Student": "Agregar Nuevo Estudiante",
    "Viewing History": "Ver Historial",
    "Managing Inventory": "Gestión de Inventario",
    "Adding/Updating Prizes": "Agregar/Actualizar Premios",
    "Redemption Log:": "Bitácora de Canjes:",
    "Inventory Report:": "Reporte de Inventario:",
    "Frequently Asked Questions": "Preguntas Frecuentes",
    "I entered the wrong points! How do I undo it?": "¡Ingresé los puntos incorrectos! ¿Cómo lo deshago?",
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