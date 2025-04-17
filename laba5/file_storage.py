from flask import Flask, request, jsonify, send_file, make_response
import os
import shutil
from datetime import datetime
import mimetypes
import json

app = Flask(__name__)

# Базовая директория для хранения файлов
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")

# Создаем хранилище, если его нет
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)


def get_absolute_path(path):
    """Получение абсолютного пути файла/директории в хранилище"""
    # Удаляем начальный слэш если есть
    if path.startswith('/'):
        path = path[1:]
    return os.path.join(STORAGE_DIR, path)


@app.route('/<path:file_path>', methods=['GET', 'PUT', 'DELETE', 'HEAD'])
@app.route('/', defaults={'file_path': ''}, methods=['GET'])
def handle_request(file_path):
    absolute_path = get_absolute_path(file_path)

    # GET запрос
    if request.method == 'GET':
        # Если путь ведет к директории, возвращаем список файлов
        if os.path.isdir(absolute_path):
            files = []

            try:
                for item in os.listdir(absolute_path):
                    item_path = os.path.join(absolute_path, item)
                    item_stat = os.stat(item_path)

                    files.append({
                        "name": item,
                        "is_dir": os.path.isdir(item_path),
                        "size": item_stat.st_size,
                        "modified": datetime.fromtimestamp(item_stat.st_mtime).isoformat()
                    })

                return jsonify({"path": file_path, "items": files})
            except FileNotFoundError:
                return jsonify({"error": "Directory not found"}), 404
            except PermissionError:
                return jsonify({"error": "Permission denied"}), 403

        # Если путь ведет к файлу, возвращаем содержимое файла
        elif os.path.isfile(absolute_path):
            try:
                return send_file(absolute_path)
            except FileNotFoundError:
                return jsonify({"error": "File not found"}), 404
            except PermissionError:
                return jsonify({"error": "Permission denied"}), 403
        else:
            return jsonify({"error": "Not found"}), 404

    # PUT запрос - загрузка файла
    elif request.method == 'PUT':
        try:
            # Создаем директории в пути, если их нет
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

            # Сохраняем файл 
            with open(absolute_path, 'wb') as f:
                # request.data может быть пустым для form data
                if request.data:
                    f.write(request.data)
                elif request.form:
                    f.write(next(iter(request.form.keys())).encode('utf-8'))
                else:
                    f.write(request.get_data())

            return jsonify({"message": "File uploaded successfully"}), 201
        except PermissionError:
            return jsonify({"error": "Permission denied"}), 403
        except IsADirectoryError:
            return jsonify({"error": "Cannot upload to a directory path"}), 400

    # DELETE запрос - удаление файла или директории
    elif request.method == 'DELETE':
        if os.path.exists(absolute_path):
            try:
                if os.path.isdir(absolute_path):
                    shutil.rmtree(absolute_path)
                    return jsonify({"message": "Directory deleted successfully"}), 200
                else:
                    os.remove(absolute_path)
                    return jsonify({"message": "File deleted successfully"}), 200
            except PermissionError:
                return jsonify({"error": "Permission denied"}), 403
        else:
            return jsonify({"error": "Not found"}), 404

    # HEAD запрос - получение информации о файле
    elif request.method == 'HEAD':
        if os.path.isfile(absolute_path):
            try:
                stat = os.stat(absolute_path)

                response = make_response('')
                response.headers['Content-Length'] = str(stat.st_size)
                response.headers['Last-Modified'] = datetime.fromtimestamp(stat.st_mtime).strftime(
                    '%a, %d %b %Y %H:%M:%S GMT')

                # Определяем MIME-тип файла
                content_type, _ = mimetypes.guess_type(absolute_path)
                if content_type:
                    response.headers['Content-Type'] = content_type

                return response
            except FileNotFoundError:
                return '', 404
            except PermissionError:
                return '', 403
        else:
            return '', 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
