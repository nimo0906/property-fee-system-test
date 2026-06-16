from server.import_data_shared import *
from server.import_templates import render_template_csv, render_template_xlsx

class ImportMixinPart3(BaseHandler):
    def _basic_import_template(self, file_type='xlsx'):
        return self._typed_import_template('basic', file_type)

    def _typed_import_template(self, template_key, file_type='xlsx'):
        if file_type == 'csv':
            data, filename = render_template_csv(template_key)
            if data is None:
                return self._not_found()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data, filename, _ = render_template_xlsx(template_key)
        if data is None:
            return self._not_found()
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
