import re

with open('template_backup.html', 'r', encoding='utf-8') as f:
    original = f.read()

# Find the main content section
main_start = original.find("<!-- ===== MAIN CONTENT ===== -->")
main_end = original.find("<!-- ===== AD SLOT BOTTOM ===== -->")

# New dynamic content section
new_section = """<!-- ===== BREADCRUMB ===== -->
<div class='breadcrumb' id='breadcrumb'></div>
<!-- ===== MAIN CONTENT ===== -->
<div id='content'>
<div class='loading'>جاري التحميل...</div>
</div>
"""

# Replace
modified = original[:main_start] + new_section + original[main_end:]

# Read the JS file
with open('novel_app.js', 'r', encoding='utf-8') as f:
    js_code = f.read()

# Add JS before </body>
modified = modified.replace('</body>', '<script>\n' + js_code + '\n</script>\n</body>')

# Also add breadcrumb CSS if not present
breadcrumb_css = """
/* ===== BREADCRUMB ===== */
.breadcrumb{max-width:1200px;margin:0 auto;padding:16px 24px;font-size:13px;color:#888;}
.breadcrumb a{color:#8B1A1A;}
.breadcrumb a:hover{text-decoration:underline;}
/* ===== LOADING ===== */
.loading{text-align:center;padding:40px;color:#999;}
.loading::after{content:'';display:inline-block;width:20px;height:20px;border:2px solid #ddd;border-top-color:#8B1A1A;border-radius:50%;animation:spin 0.8s linear infinite;margin-right:8px;vertical-align:middle;}
@keyframes spin{to{transform:rotate(360deg);}}
"""

# Insert CSS before </style>
modified = modified.replace('</style>', breadcrumb_css + '</style>')

with open('template_v3.html', 'w', encoding='utf-8') as f:
    f.write(modified)

print('Template v3 created. Length:', len(modified))
