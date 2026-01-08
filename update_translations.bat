@echo off
echo ========================================================
echo  1. Extracting new text from app.py and templates...
echo ========================================================
pybabel extract -F babel.cfg -k _ -k _l -o messages.pot .

echo.
echo ========================================================
echo  2. Updating the Spanish translation file...
echo ========================================================
pybabel update -i messages.pot -d translations

echo.
echo ========================================================
echo  DONE! 
echo  Now open: translations/es/LC_MESSAGES/messages.po
echo  Add the Spanish translations for the new strings.
echo  Then run: pybabel compile -d translations
echo ========================================================
pause