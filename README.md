# chandra-pdf-extract

Небольшой CLI-проект для извлечения текста и вёрстки из PDF с помощью **Chandra OCR** ([`chandra-ocr`](https://pypi.org/project/chandra-ocr/)) через **vLLM** (отдельный сервер, клиент по HTTP).

## Возможности

- Один PDF целиком или выбранные страницы (`-p`).
- Все PDF из каталога `documents/` (или другого пути).
- Вывод **Markdown** (и опционально **HTML**) по одному файлу на страницу: `outputs/<stem>/page_NNN.md`.
- **Лог в реальном времени**: время растеризации страницы, время инференса Chandra, метка времени строки.
- **Итог после завершения**: общее время, число страниц, min/max/avg времени инференса, суммарное время по каждому документу.

## Требования

- Python **3.10+**
- Запущенный vLLM-сервер с моделью Chandra (см. раздел ниже).

## Установка

```bash
cd chandra-pdf-extract
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Скопируйте настройки окружения (Chandra читает файл **`local.env`** в текущей директории или родителях):

```bash
cp local.env.example local.env
# отредактируйте VLLM_API_BASE/VLLM_MODEL_NAME и при необходимости MAX_OUTPUT_TOKENS
```

Положите PDF в каталог **`documents/`** или передавайте путь к файлу аргументом.

## Запуск

Установка добавляет команду **`chandra-extract-pdf`** (или `python -m chandra_pdf_extract`).

### Один документ, все страницы

```bash
chandra-extract-pdf documents/report.pdf --output-dir outputs/
```

### Один документ, отдельные страницы

```bash
chandra-extract-pdf documents/report.pdf -p 1
chandra-extract-pdf documents/report.pdf -p 1,3-5,10
```

### Все PDF в каталоге

```bash
chandra-extract-pdf --documents-dir documents/ --output-dir outputs/
```

Опция **`-p` / `--pages`** для режима каталога **не применяется** (обрабатываются все страницы каждого файла); для выборочных страниц запускайте по одному файлу.

### Бэкенд и промпт

```bash
# Используется только vLLM (сервер должен быть уже запущен)
chandra-extract-pdf file.pdf
```

```bash
chandra-extract-pdf file.pdf --prompt-type ocr_layout   # по умолчанию
chandra-extract-pdf file.pdf --prompt-type ocr
```

### Дополнительно

- `--render-scale 2.0` — масштаб растеризации PyMuPDF (выше = четче и тяжелее).
- `--html` — сохранять ещё и `page_NNN.html`.
- `--max-output-tokens N` — ограничение длины генерации на страницу.

Код возврата: **0** при успехе всех страниц, **2** если хотя бы одна страница завершилась с ошибкой, **130** при прерывании по Ctrl+C (после вывода summary).

## vLLM на сервере

1. Установите и запустите сервер по инструкции пакета **`chandra-ocr`** (entrypoint `chandra_vllm` и переменные `VLLM_*`).
2. В `local.env` задайте `VLLM_API_BASE` и при необходимости `VLLM_MODEL_NAME`.
3. Запускайте CLI без выбора бэкенда: используется только vLLM.

### Локальный скрипт запуска vLLM

В проект добавлен скрипт `scripts/run-vllm.sh`, который запускает контейнер vLLM с моделью Chandra и автоматически подбирает профиль по GPU:

- **H100**: `dtype=bfloat16`, `max_num_seqs=96`, `max_num_batched_tokens=8192`
- **V100**: `dtype=half`, `max_num_seqs=32`, `max_num_batched_tokens=4096`
- если GPU не распознан — безопасный generic-профиль (`half`, `32`, `4096`)

```bash
./scripts/run-vllm.sh
```

Любой параметр можно переопределить через переменные окружения:

```bash
VLLM_DTYPE=half VLLM_MAX_NUM_SEQS=48 VLLM_MAX_NUM_BATCHED_TOKENS=6144 ./scripts/run-vllm.sh
```

### Скрипт установки vLLM

Для подготовки окружения в проекте добавлен `scripts/install-vllm.sh`:

```bash
./scripts/install-vllm.sh
```

Скрипт:
- ставит `docker.io`, `nvidia-container-toolkit`, `ubuntu-drivers-common`;
- настраивает NVIDIA runtime для Docker;
- создаёт `.venv` (если нет), устанавливает Python-зависимости проекта и `vllm`;
- создаёт `local.env` из `local.env.example`, если файла ещё нет.

### Тест подбора `--concurrent-sequences`

Для сравнения производительности добавлен скрипт `scripts/benchmark-concurrency.sh`:

```bash
./scripts/benchmark-concurrency.sh documents/Data1_2_2069_index.pdf 1-8
```

По умолчанию проверяются значения `1 2 3 4 6 8`, для каждого запускается `chandra-extract-pdf`, а затем выводится сводная таблица и сохраняется файл результатов (`.tsv`) в `outputs/bench_concurrency/`.

Через переменные окружения можно переопределить параметры:

```bash
CONCURRENCY_LIST="2 4 6" MAX_OUTPUT_TOKENS=4096 RENDER_SCALE=1.5 ./scripts/benchmark-concurrency.sh documents/Data1_2_2069_index.pdf 1-6
```

## Структура проекта

```
chandra-pdf-extract/
  documents/          # PDF для батча (пример, добавьте свои файлы)
  src/chandra_pdf_extract/
    cli.py            # точка входа, логирование и summary
    engine.py         # обёртка над InferenceManager
    pdf_render.py     # PDF → PIL через PyMuPDF
    pagespec.py       # разбор -p 1,3-5
  local.env.example
  README.md
```

## Лицензия

Конфигурация и скрипты этого репозитория: **Apache-2.0** (как у `chandra-ocr`). Условия весов модели см. на странице модели на Hugging Face.
