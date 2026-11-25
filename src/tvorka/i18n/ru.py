"""Russian translations: {English source string: Russian text}.

``tests/unit/test_i18n.py`` fails when a ``tr("...")`` string in the code has no entry here.
"""

RU: dict[str, str] = {
    "Add LoRA": "Добавить LoRA",
    "LoRA": "LoRA",
    "LoRA weight": "Вес LoRA",
    "Remove LoRA": "Убрать LoRA",
    "Choose adapters made for the selected model family.": "Выбирайте адаптеры для семейства выбранной модели.",
    "This model generates at a fixed size.": "Модель генерирует в фиксированном размере.",
    "The requested size exceeds the model's direct generation limit.":
        "Запрошенный размер превышает предел прямой генерации модели.",
    "{w} × {h} px — the model draws {gw} × {gh}, then adjusts to the requested size":
        "{w} × {h} px — модель рисует {gw} × {gh}, затем изображение приводится к нужному размеру",
    "The edges are cropped to fill the requested proportions.": "Края обрезаются под запрошенные пропорции.",
    "No usable audio format for this microphone.": "Не найден подходящий формат записи для микрофона.",
    "The microphone could not start recording.": "Микрофон не смог начать запись.",
    "The microphone stopped recording.": "Микрофон прекратил запись.",
    # --- engine errors -------------------------------------------------------------
    "Something went wrong. Details are in the log (Settings → Open log).":
        "Что-то пошло не так. Подробности — в журнале (Настройки → Открыть журнал).",
    "The model is not downloaded yet. Download it on the Models page.":
        "Модель ещё не скачана. Скачайте её на странице «Модели».",
    "The model could not be loaded. Its files may be damaged — "
    "delete it on the Models page and download it again.":
        "Не удалось загрузить модель. Возможно, файлы повреждены — удалите её на странице «Модели» "
        "и скачайте заново.",
    "The graphics card is not available to PyTorch. Check the diagnostics in "
    "Settings → This computer, or switch to the CPU-only mode.":
        "Видеокарта недоступна для PyTorch. Посмотрите диагностику в разделе «Настройки → Этот компьютер» "
        "или включите режим «Только процессор».",
    "This model cannot use a reference in this mode. "
    "Choose another reference mode or remove the reference.":
        "Эта модель не умеет работать с референсом в таком режиме. Выберите другой режим референса "
        "или уберите его.",
    "The reference image could not be opened. Use a PNG, JPG or WebP file.":
        "Не удалось открыть референс. Используйте файл PNG, JPG или WebP.",
    "This model needs a reference image as the first frame. "
    "Add one and try again.":
        "Этой модели нужен референс — первый кадр. Добавьте изображение и повторите.",
    "The style adapter could not be loaded. Check the internet connection — "
    "it is downloaded on first use.":
        "Не удалось загрузить адаптер стиля. Проверьте подключение к интернету — "
        "он скачивается при первом использовании.",
    "This model does not support LoRA. Remove the LoRA or pick another model.":
        "Эта модель не поддерживает LoRA. Уберите LoRA или выберите другую модель.",
    "The LoRA could not be attached. Make sure it was made for this model family.":
        "Не удалось подключить LoRA. Убедитесь, что она сделана для этого семейства моделей.",
    "There is nothing to read aloud. Enter some text.":
        "Нечего озвучивать. Введите текст.",
    "This model type is not supported yet.":
        "Модели такого типа пока не поддерживаются.",
    "The online voice component is not installed. Reinstall Tvorka "
    "or choose a local voice model.":
        "Компонент онлайн-голосов не установлен. Переустановите Tvorka или выберите локальную модель речи.",
    "No connection to the service. Check the internet connection and try again.":
        "Нет связи с сервисом. Проверьте подключение к интернету и повторите.",
    "The model is no longer in the list. Pick another model.":
        "Этой модели больше нет в списке. Выберите другую.",
    "This computer cannot run the model. The reason is shown under the model name.":
        "Этот компьютер не потянет модель. Причина указана под её названием.",
    "Not enough video memory. Lower the resolution or choose the "
    "“Low memory” mode in Settings.":
        "Не хватило видеопамяти. Уменьшите разрешение или выберите режим «Экономия памяти» в настройках.",
    # --- window and navigation -----------------------------------------------------
    "Image": "Изображение",
    "Video": "Видео",
    "Voice": "Озвучка",
    "Models": "Модели",
    "Gallery": "Галерея",
    "Settings": "Настройки",
    "This computer": "Этот компьютер",
    "Detecting hardware…": "Определяем железо…",
    "No graphics card — the processor will be used": "Видеокарты нет — будет использован процессор",
    "See Settings → This computer": "См. «Настройки → Этот компьютер»",
    "VRAM {used:.1f} / {total:.1f} GB": "VRAM {used:.1f} / {total:.1f} ГБ",
    "No model loaded": "Модель не загружена",
    "Unload the model and free memory": "Выгрузить модель и освободить память",
    "Queue: {count}": "В очереди: {count}",
    "Quit Tvorka": "Выход из Tvorka",
    "Generation or a download is in progress. Stop it and quit?":
        "Идёт генерация или загрузка. Прервать и выйти?",
    "Tvorka is already running.": "Tvorka уже запущена.",
    "Close": "Закрыть",
    # --- common widgets ------------------------------------------------------------
    "random": "случайный",
    "New random seed": "Новый случайный сид",
    "Use the last seed": "Повторить последний сид",
    "Use the last seed ({seed})": "Повторить последний сид ({seed})",
    "Width": "Ширина",
    "Height": "Высота",
    "Keep proportions": "Сохранять пропорции",
    "VRAM {need:.1f} / {have:.1f} GB": "VRAM {need:.1f} / {have:.1f} ГБ",
    "RAM {need:.1f} / {have:.1f} GB": "ОЗУ {need:.1f} / {have:.1f} ГБ",
    "The result will appear here": "Здесь появится результат",
    "Results of this session will line up here": "Здесь выстроятся результаты этого сеанса",
    "Reference image": "Референс",
    "Drop an image, click to choose or press Ctrl+V":
        "Перетащите изображение, нажмите, чтобы выбрать, или вставьте Ctrl+V",
    "Remove the reference": "Убрать референс",
    "Choose a reference image": "Выбор референса",
    # --- image page ----------------------------------------------------------------
    "Model": "Модель",
    "Prompt": "Промт",
    "Negative prompt": "Негативный промт",
    "What to avoid (optional)": "Чего избегать (необязательно)",
    "Structure": "Структура",
    "Style": "Стиль",
    "Edit": "Редактирование",
    "Keeps the composition of the reference; strength sets how much is redrawn.":
        "Сохраняет композицию референса; сила — насколько сильно он перерисовывается.",
    "Borrows the look of the reference; strength sets how closely it is followed.":
        "Перенимает стиль референса; сила — насколько точно ему следовать.",
    "The model edits the reference according to the prompt.": "Модель правит референс по промту.",
    "Strength": "Сила",
    "Format": "Формат",
    "Proportions": "Пропорции",
    "Exact size": "Точный размер",
    "Size": "Размер",
    "Native": "Родной",
    "Enlarging": "Увеличение",
    "Quality (Real-ESRGAN)": "Качественно (Real-ESRGAN)",
    "Fast": "Быстро",
    "File": "Файл",
    "{w} × {h} px": "{w} × {h} px",
    "{w} × {h} px — the model draws {gw} × {gh}, then it is enlarged":
        "{w} × {h} px — модель рисует {gw} × {gh}, затем изображение увеличивается",
    "Steps": "Шаги",
    "Prompt strength": "Сила промта",
    "How strictly the model follows the prompt.": "Насколько строго модель следует промту.",
    "Seed": "Сид",
    "Images": "Изображения",
    "Number of images": "Количество картинок",
    "Cancel (Esc)": "Отмена (Esc)",
    "Downloading": "Загрузка",
    "Download ({size:.1f} GB)": "Скачать ({size:.1f} ГБ)",
    "Add to queue": "В очередь",
    "Create": "Создать",
    "Waiting in the queue…": "Ожидание в очереди…",
    "Save as…": "Сохранить как…",
    "Save as": "Сохранить как",
    "Show in folder": "Показать в папке",
    "Copy to clipboard": "Копировать в буфер обмена",
    "Use as reference": "Использовать как референс",
    "Repeat with this seed": "Повторить с этим сидом",
    "Send to Video as the first frame": "Отправить в «Видео» как первый кадр",
    "seed": "сид",
    "Image copied": "Изображение скопировано",
    # --- redesign: window, image page, settings -----------------------------------
    "Local AI studio": "Локальная ИИ-студия",
    "In memory: {name}": "В памяти: {name}",
    "v{version} · by {author}": "v{version} · автор {author}",
    "Describe an idea — the model draws it right on your computer.":
        "Опишите идею — модель нарисует её прямо на вашем компьютере.",
    "A lighthouse on a cliff at dusk, warm light, film photo…":
        "Маяк на скале в сумерках, тёплый свет, плёночное фото…",
    "Tip: most models understand English best.": "Совет: большинство моделей лучше понимают английский.",
    "Reference (optional)": "Референс (необязательно)",
    "Advanced": "Дополнительно",
    "More steps — more detail, but slower.": "Больше шагов — больше деталей, но дольше.",
    "The same seed and settings repeat a picture.": "Тот же сид и настройки повторяют картинку.",
    "How many images to create": "Сколько картинок создать",
    "Create (Ctrl+Enter)": "Создать (Ctrl+Enter)",
    "What shall we create?": "Что создадим?",
    "Pick an idea to start from, or write your own on the left.":
        "Выберите идею для старта или напишите свою слева.",
    "Cozy reading nook by a rainy window": "Уютный уголок у дождливого окна",
    "Tiny island with a lighthouse, 3D": "Крошечный остров с маяком, 3D",
    "Portrait of an old sailor in oil": "Портрет старого моряка маслом",
    "Night street food stall in the rain": "Ночной уличный ларёк под дождём",
    "Changes are saved automatically.": "Изменения сохраняются автоматически.",
    "Appearance": "Внешний вид",
    "Language": "Язык",
    "Theme": "Тема",
    "Dark": "Тёмная",
    "Light": "Светлая",
    "Performance": "Производительность",
    "Memory mode": "Режим памяти",
    "Automatic": "Автоматически",
    "Tvorka picks the fastest mode that fits this computer.":
        "Tvorka сама выберет самый быстрый режим, который подходит этому компьютеру.",
    "Speed": "Скорость",
    "The whole model stays on the graphics card. Needs the most video memory.":
        "Вся модель находится на видеокарте. Нужно больше всего видеопамяти.",
    "Balanced": "Баланс",
    "Low memory": "Экономия памяти",
    "The model is streamed piece by piece. Slow, but runs on small graphics cards.":
        "Модель подгружается по частям. Медленно, но работает даже на слабых видеокартах.",
    "Processor only": "Только процессор",
    "No graphics card is used. Works everywhere, but very slowly.":
        "Видеокарта не используется. Работает везде, но очень медленно.",
    "Keep the model in memory between generations": "Держать модель в памяти между генерациями",
    "Faster repeats; turn off to free memory for other programs.":
        "Повторные генерации быстрее; выключите, чтобы освобождать память для других программ.",
    "Folders": "Папки",
    "Results": "Результаты",
    "Data and logs": "Данные и журнал",
    "Open": "Открыть",
    "Access token": "Токен доступа",
    "Needed only for models with restricted access. Stored on this computer in plain text in settings.json.":
        "Нужен только для моделей с ограниченным доступом. Хранится на этом компьютере открытым текстом в settings.json.",
    "About": "О программе",
    "A free studio for images, video and voice made by AI models that run on your own computer.":
        "Бесплатная студия для создания изображений, видео и озвучки ИИ-моделями, которые работают на вашем компьютере.",
    "Author of the implementation:": "Автор реализации:",
    "Author on GitHub": "Автор на GitHub",
    "Project page": "Страница проекта",
    "Open log": "Открыть журнал",
    "Model licenses are set by their authors; some allow only non-commercial use. The license is shown on each model's card.":
        "Лицензии моделей задают их авторы; некоторые разрешают только некоммерческое использование. Лицензия указана в карточке каждой модели.",
    # --- models page ---------------------------------------------------------------
    "Download ready-made models, find more on Hugging Face or add your own.":
        "Скачайте готовые модели, найдите новые на Hugging Face или добавьте свою.",
    "Models take {used} · {free} free": "Модели занимают {used} · свободно {free}",
    "Catalog": "Каталог",
    "Installed": "Установленные",
    "All": "Все",
    "Add your own": "Добавить свою",
    "Add your own model": "Своя модель",
    "Folder": "Папка",
    "Browse…": "Обзор…",
    "Check": "Проверить",
    "Checking…": "Проверяем…",
    "author/model or a link to its Hugging Face page": "автор/модель или ссылка на её страницу на Hugging Face",
    "Folder with a diffusers, transformers or GGUF model": "Папка с моделью diffusers, transformers или GGUF",
    "A .safetensors / .ckpt checkpoint, a Silero .pt or a .gguf chat model":
        "Чекпойнт .safetensors / .ckpt, файл Silero .pt или чат-модель .gguf",
    "Choose a model folder": "Выбор папки модели",
    "Choose a model file": "Выбор файла модели",
    "Recognized. Check the details and add it to your models.":
        "Модель распознана. Проверьте данные и добавьте её в свои модели.",
    "Add to my models": "Добавить в мои модели",
    "{name} added": "Модель «{name}» добавлена",
    "Search Hugging Face: flux, anime, portrait, tts…": "Поиск на Hugging Face: flux, anime, portrait, tts…",
    "Searching…": "Ищем…",
    "Nothing found. Try another word.": "Ничего не найдено. Попробуйте другое слово.",
    "{count} downloads · {likes} likes": "{count} загрузок · {likes} отметок",
    "In your list": "Уже в списке",
    "Check and add": "Проверить и добавить",
    "Nothing installed yet. Pick a model in the Catalog and press Download.":
        "Пока ничего не установлено. Выберите модель в каталоге и нажмите «Скачать».",
    "No models of this kind.": "Моделей такого вида нет.",
    "Restricted access: needs a Hugging Face token": "Ограниченный доступ: нужен токен Hugging Face",
    "Open the model page": "Открыть страницу модели",
    "Cancel the download": "Отменить загрузку",
    "Delete from disk": "Удалить с диска",
    "Remove from the list": "Убрать из списка",
    "no download": "без загрузки",
    "installed · {size}": "установлена · {size}",
    "{mb:.0f} MB": "{mb:.0f} МБ",
    "{gb:.1f} GB": "{gb:.1f} ГБ",
    "s": "с",
    "Downloading…": "Загрузка…",
    "Use": "Использовать",
    "Download": "Скачать",
    "Checking this computer…": "Проверяем этот компьютер…",
    "Delete model": "Удаление модели",
    "Remove “{name}” from the list? Its files on disk stay where they are.":
        "Убрать «{name}» из списка? Файлы на диске останутся на месте.",
    "Delete “{name}” ({size}) from disk? This cannot be undone; you can download it again.":
        "Удалить «{name}» ({size}) с диска? Отменить нельзя, но модель можно скачать заново.",
    "{name} is ready to use": "Модель «{name}» готова к работе",
    "This section is not available yet.": "Этот раздел пока недоступен.",
    # --- voice page ----------------------------------------------------------------
    "Type or paste text — a local model reads it aloud.":
        "Введите или вставьте текст — локальная модель прочитает его вслух.",
    "Hello! This is how your text will sound. Numbers like 2026 are read as words.":
        "Привет! Так прозвучит ваш текст. Числа вроде 2026 читаются словами.",
    "Text": "Текст",
    "{chars} characters · about {seconds:.0f} s of speech": "Символов: {chars} · около {seconds:.0f} с речи",
    "This voice works over the internet: your text is sent to Microsoft.":
        "Этот голос работает через интернет: ваш текст отправляется в Microsoft.",
    "Voice and sound": "Голос и звук",
    "Default voice": "Голос по умолчанию",
    "Speaker": "Голос",
    "Listen": "Прослушать",
    "Hear a short sample of this voice": "Прослушать короткий образец голоса",
    "Hello! This is how this voice sounds.": "Привет! Так звучит этот голос.",
    "Read aloud": "Озвучить",
    "Read aloud (Ctrl+Enter)": "Озвучить (Ctrl+Enter)",
    "Download ({size})": "Скачать ({size})",
    "Your voice-overs": "Ваши озвучки",
    "Your voice-overs will appear here. Write a few sentences on the left and press “Read aloud”.":
        "Здесь появятся ваши озвучки. Напишите пару предложений слева и нажмите «Озвучить».",
    "Play": "Воспроизвести",
    "Read answer aloud": "Озвучить ответ",
    "Answer audio": "Озвучка ответа",
    "Playback position": "Позиция воспроизведения",
    "The audio file is missing.": "Аудиофайл не найден.",
    "Could not play the audio.": "Не удалось воспроизвести аудио.",
    "Speech synthesis did not finish.": "Озвучка не завершилась.",
    "Pause": "Пауза",
    # --- video page ----------------------------------------------------------------
    "Describe a scene and its motion — or bring it to life from a picture.":
        "Опишите сцену и движение — или оживите картинку.",
    "A paper boat floating on a calm lake at sunset, gentle ripples, slow camera pan…":
        "Бумажный кораблик на спокойном озере на закате, лёгкая рябь, медленная панорама…",
    "First frame (optional)": "Первый кадр (необязательно)",
    "Drop a picture to bring it to life, click to choose or press Ctrl+V":
        "Перетащите картинку, чтобы оживить её, нажмите, чтобы выбрать, или вставьте Ctrl+V",
    "This model needs a first frame: it animates a picture.":
        "Этой модели нужен первый кадр: она оживляет картинку.",
    "Duration": "Длительность",
    "Frame rate": "Частота кадров",
    "As the model": "Как у модели",
    "{frames} frames at {fps} fps · {seconds:.1f} s": "{frames} кадров при {fps} к/с · {seconds:.1f} с",
    "this is the model's limit": "это предел модели",
    "{w} × {h} px — the model films {gw} × {gh}, then frames are enlarged":
        "{w} × {h} px — модель снимает {gw} × {gh}, затем кадры увеличиваются",
    "Your video will play here. Describe a scene on the left and press “Create”.":
        "Здесь будет играть ваше видео. Опишите сцену слева и нажмите «Создать».",
    "Previous frame": "Предыдущий кадр",
    "Next frame": "Следующий кадр",
    "text encoder": "текстовый энкодер",
    "second text encoder": "второй текстовый энкодер",
    "main network": "основная сеть",
    "image decoder": "декодер изображения",
    # --- settings: computer, folders, formats, catalog, plugins ---------------------
    "Diagnostics": "Диагностика",
    "Processor: {name} · {cores} cores / {threads} threads": "Процессор: {name} · ядер {cores}, потоков {threads}",
    "Memory: {total:.1f} GB, {free:.1f} GB free": "Оперативная память: {total:.1f} ГБ, свободно {free:.1f} ГБ",
    "Graphics: {name}": "Видеокарта: {name}",
    "Graphics: none found": "Видеокарта: не найдена",
    "{gb:.1f} GB of video memory": "видеопамять {gb:.1f} ГБ",
    "driver {version}": "драйвер {version}",
    "PyTorch: not installed": "PyTorch: не установлен",
    "Free space for models: {size}": "Свободно для моделей: {size}",
    "No problems found. Tvorka uses this computer to the full.":
        "Проблем не найдено. Tvorka использует этот компьютер в полную силу.",
    "PyTorch is not installed, so nothing can be generated. Reinstall Tvorka.":
        "PyTorch не установлен, поэтому генерация невозможна. Переустановите Tvorka.",
    "No graphics card found: models will run on the processor. Prefer the lightest models.":
        "Видеокарта не найдена: модели будут работать на процессоре. Выбирайте самые лёгкие.",
    "Less than 16 GB of RAM: heavy models may not fit.":
        "Оперативной памяти меньше 16 ГБ: тяжёлые модели могут не поместиться.",
    "PyTorch without support for this graphics card is installed: generation runs on the processor, tens of times slower.":
        "Установлен PyTorch без поддержки этой видеокарты: генерация идёт на процессоре, в десятки раз медленнее.",
    "{gpu} is not supported: Tvorka works with NVIDIA, AMD Radeon RX 6000 and newer, Intel Arc and Apple Silicon graphics. Models will run on the processor.":
        "{gpu} не поддерживается: Tvorka работает с видеокартами NVIDIA, AMD Radeon RX 6000 и новее, Intel Arc и Apple Silicon. Модели будут работать на процессоре.",
    "processor only": "только процессор",
    "Set up Tvorka for {gpu}": "Настроить Tvorka для {gpu}",
    "Running from source: install the build with\n{command}": "Запуск из исходников: установите сборку командой\n{command}",
    "Tvorka closes, downloads the components for the graphics card (2–4 GB) and starts again. If the graphics driver is too old, it stays on the processor version — update the driver first.":
        "Tvorka закроется, скачает компоненты для видеокарты (2–4 ГБ) и запустится снова. Если драйвер видеокарты слишком старый, останется версия для процессора — сначала обновите драйвер.",
    "Install the GPU version of PyTorch (about 3 GB)": "Установить GPU-версию PyTorch (около 3 ГБ)",
    "Download the Tvorka build for NVIDIA graphics cards from the project page.":
        "Скачайте сборку Tvorka для видеокарт NVIDIA со страницы проекта.",
    "PyTorch is already loaded in this session. Restart Tvorka and press the button before creating anything.":
        "PyTorch уже загружен в этом сеансе. Перезапустите Tvorka и нажмите кнопку до первой генерации.",
    "Downloading and installing… This takes several minutes.": "Скачиваем и устанавливаем… Это займёт несколько минут.",
    "Installed. Restart Tvorka to use the graphics card.":
        "Установлено. Перезапустите Tvorka, чтобы задействовать видеокарту.",
    "The GPU version of PyTorch is installed. Restart Tvorka.": "GPU-версия PyTorch установлена. Перезапустите Tvorka.",
    "Installation failed. Check the internet connection; details are in the log.":
        "Установка не удалась. Проверьте подключение к интернету; подробности — в журнале.",
    "Change…": "Изменить…",
    "Choose a folder": "Выбор папки",
    "Wait until downloads and generation finish, then change the folder.":
        "Дождитесь окончания загрузок и генерации, затем меняйте папку.",
    "Tvorka cannot write to this folder. Choose another one.": "Tvorka не может записывать в эту папку. Выберите другую.",
    "Models from the previous folder were not moved: {old}. Copy its contents here or download the models again.":
        "Модели из прежней папки не перенесены: {old}. Скопируйте её содержимое сюда или скачайте модели заново.",
    "Default file formats": "Форматы файлов по умолчанию",
    "PNG keeps the generation settings inside the file. MP4 plays everywhere; WebM is smaller; GIF suits messengers. WAV is lossless, MP3 is compact.":
        "PNG хранит настройки генерации внутри файла. MP4 открывается везде, WebM компактнее, GIF подходит для мессенджеров. WAV — без потерь, MP3 — компактный.",
    "Model catalog": "Каталог моделей",
    "Catalog address": "Адрес каталога",
    "A YAML list of models. Only Hugging Face repositories and trusted hosts are accepted from it; it never contains code.":
        "Список моделей в формате YAML. Из него принимаются только репозитории Hugging Face и доверенные сайты; кода в нём не бывает.",
    "Check for new models when Tvorka starts": "Проверять новые модели при запуске Tvorka",
    "Update now": "Обновить сейчас",
    "Tell me when a new version of Tvorka is released": "Сообщать о выходе новой версии Tvorka",
    "Tvorka {version} is available.": "Доступна новая версия Tvorka {version}.",
    "Open the page": "Открыть страницу",
    "Default address": "Адрес по умолчанию",
    "The address must start with https://": "Адрес должен начинаться с https://",
    "Catalog updated: {count} models.": "Каталог обновлён: моделей — {count}.",
    "Could not update the catalog: {reason}": "Не удалось обновить каталог: {reason}",
    "Plugins": "Плагины",
    "No plugins. A plugin adds a new engine for models that Tvorka cannot run yet.":
        "Плагинов нет. Плагин добавляет движок для моделей, которые Tvorka пока не умеет запускать.",
    "{name}: not loaded — {reason}": "{name}: не загружен — {reason}",
    "{name}: engines {engines}": "{name}: движки {engines}",
    "Plugins are Python code: put only files you trust in this folder. Changes apply after a restart.":
        "Плагины — это код на Python: кладите в эту папку только то, чему доверяете. Изменения применяются после перезапуска.",
    "Plugins folder": "Папка плагинов",
    # --- welcome screen --------------------------------------------------------------
    "Welcome": "Добро пожаловать",
    "Welcome screen": "Экран приветствия",
    "Welcome to Tvorka": "Добро пожаловать в Tvorka",
    "Create images, video and voice-overs with AI models right on your computer — free, and your ideas never leave it.":
        "Создавайте изображения, видео и озвучку ИИ-моделями прямо на своём компьютере — бесплатно, и ваши идеи никуда не уходят.",
    "From a prompt or a reference, in any size up to 4K and beyond.":
        "По описанию или референсу, в любом размере — до 4K и больше.",
    "Short clips from a description, or bring a picture to life.": "Короткие ролики по описанию — или оживите картинку.",
    "Natural speech from text, numbers are read as words.": "Естественная речь из текста, числа читаются словами.",
    "Your computer: {graphics} · {ram:.0f} GB of RAM": "Ваш компьютер: {graphics} · {ram:.0f} ГБ оперативной памяти",
    "{name}, {vram:.0f} GB of video memory": "{name}, видеопамять {vram:.0f} ГБ",
    "no graphics card": "видеокарты нет",
    "Generation will run on the processor; see Settings → This computer.":
        "Генерация будет идти на процессоре; подробности — в разделе «Настройки → Этот компьютер».",
    "Recommended to start": "Рекомендуем для начала",
    "Tvorka picked one model of each kind that suits this computer best. You can add more any time on the Models page.":
        "Tvorka подобрала по одной модели каждого вида, которые лучше всего подходят этому компьютеру. Другие можно добавить в любой момент в разделе «Модели».",
    "Choosing models for this computer…": "Подбираем модели для этого компьютера…",
    "installed": "установлена",
    "To download: {size} · {free} free on disk": "Будет скачано: {size} · свободно на диске {free}",
    "Download selected and start": "Скачать выбранное и начать",
    "Start creating": "Начать творить",
    "Skip for now": "Пропустить",
    "Downloads started. Progress is shown on the Create button and on the Models page.":
        "Загрузка началась. Прогресс виден на кнопке «Создать» и в разделе «Модели».",
    # --- gallery -------------------------------------------------------------------
    "{count} works": "Работ: {count}",
    "Nothing here yet": "Пока пусто",
    "Everything you create will be collected here.": "Здесь соберётся всё, что вы создадите.",
    "No works of this kind yet.": "Работ такого вида пока нет.",
    "Create the first image": "Создать первую картинку",
    "Repeat these settings": "Повторить с этими настройками",
    "Delete": "Удалить",
    "Delete this work and its file from disk? This cannot be undone.":
        "Удалить эту работу и её файл с диска? Отменить нельзя.",
    "{seconds} s": "{seconds} с",
    # --- progress stages -----------------------------------------------------------
    "Starting the engine…": "Запуск движка…",
    "Loading the model…": "Загрузка модели…",
    "Placing the model in memory…": "Размещение модели в памяти…",
    "Model ready": "Модель готова",
    "Generating…": "Генерация…",
    "Saving…": "Сохранение…",
    "Encoding the video…": "Кодирование видео…",
    "Enlarging the image…": "Увеличение изображения…",
    "Synthesizing speech…": "Синтез речи…",
    "Downloading additional files…": "Загрузка дополнительных файлов…",
    "Not enough memory — retrying in a leaner mode…":
        "Не хватило памяти — повтор в более экономном режиме…",
    # --- verdicts ------------------------------------------------------------------
    "Runs great": "Отлично подходит",
    "Runs well": "Подходит",
    "Slow": "Медленно",
    "Very slow": "Очень медленно",
    "Will not run": "Не запустится",
    # --- advisor notes -------------------------------------------------------------
    "Works over the internet: the text is sent to Microsoft.":
        "Работает через интернет: текст отправляется в Microsoft.",
    "PyTorch without graphics card support is installed. "
    "Install the GPU build in Settings → This computer.":
        "Установлен PyTorch без поддержки видеокарты. Установите GPU-сборку в разделе "
        "«Настройки → Этот компьютер».",
    "{gpu} is not supported yet; the model will run on the processor.":
        "{gpu} пока не поддерживается — модель будет работать на процессоре.",
    "Not enough disk space: {need:.1f} GB needed, {have:.1f} GB free.":
        "Не хватает места на диске: нужно {need:.1f} ГБ, свободно {have:.1f} ГБ.",
    "Runs on the processor — expect minutes instead of seconds.":
        "Работает на процессоре — счёт пойдёт на минуты, а не секунды.",
    "Needs about {need:.0f} GB of RAM, this computer has {have:.0f} GB.":
        "Нужно около {need:.0f} ГБ оперативной памяти, а в этом компьютере {have:.0f} ГБ.",
    "Needs about {need:.0f} GB of RAM out of {have:.0f} GB — "
    "Windows will use the page file, which is much slower.":
        "Нужно около {need:.0f} ГБ оперативной памяти из {have:.0f} ГБ — Windows задействует файл подкачки, "
        "это намного медленнее.",
    "Needs at least {need:.1f} GB of video memory, the graphics card has {have:.1f} GB.":
        "Нужно не меньше {need:.1f} ГБ видеопамяти, а у видеокарты {have:.1f} ГБ.",
    "Part of the model ({parts}) is streamed from RAM to fit the graphics card.":
        "Часть модели ({parts}) подгружается из оперативной памяти по ходу работы, чтобы уместиться в видеокарту.",
    "The model is streamed into video memory piece by piece: it fits, but slowly.":
        "Модель подгружается в видеопамять по частям: поместится, но будет медленно.",
    "Model parts take turns on the graphics card: a little slower, much less memory.":
        "Части модели по очереди занимают видеокарту: чуть медленнее, но памяти нужно намного меньше.",
    "The selected performance mode needs more video memory than available; "
    "generation may be very slow.":
        "Выбранный режим производительности требует больше видеопамяти, чем есть; "
        "генерация может идти очень медленно.",
    "The resolution is above what the model was trained on; details may repeat.":
        "Разрешение выше того, на котором обучалась модель; детали могут повторяться.",
    "Other programs occupy video memory ({free:.1f} GB free) — close them for full speed.":
        "Видеопамять занята другими программами (свободно {free:.1f} ГБ) — закройте их для полной скорости.",
    # --- hub / download errors -----------------------------------------------------
    "Access to this model is restricted. Accept its license on the Hugging Face page "
    "and enter your token in Settings.":
        "Доступ к модели ограничен. Примите её лицензию на странице Hugging Face и укажите токен в настройках.",
    "The model was not found. Check the name or the link.":
        "Модель не найдена. Проверьте название или ссылку.",
    "No connection to Hugging Face. Check the internet connection and try again.":
        "Нет связи с Hugging Face. Проверьте подключение к интернету и повторите.",
    "Enter the model as “author/name” or paste a link to its Hugging Face page.":
        "Укажите модель в виде «автор/название» или вставьте ссылку на её страницу на Hugging Face.",
    "This is an add-on (LoRA, adapter or ControlNet), not a standalone model.":
        "Это дополнение (LoRA, адаптер или ControlNet), а не самостоятельная модель.",
    "Tvorka cannot run this kind of model yet.":
        "Tvorka пока не умеет запускать модели такого типа.",
    "Not enough disk space for the download. Free some space or choose another "
    "models folder in Settings.":
        "Не хватает места на диске для загрузки. Освободите место или выберите другую папку моделей в настройках.",
    # --- chat models -----------------------------------------------------------------
    "{share} % of the model fits on the graphics card, the rest runs on the "
    "processor — answers come slower.":
        "{share} % модели помещается в видеокарту, остальное считает процессор — ответы будут медленнее.",
    "Answers are written by the processor: a few words per second.":
        "Ответы пишет процессор: несколько слов в секунду.",
    "The experts of {layers} of {total} layers stay in RAM, the rest is on the graphics "
    "card: each word needs only a few experts.":
        "Эксперты {layers} из {total} слоёв лежат в оперативной памяти, остальное — на видеокарте: "
        "на каждое слово модель берёт лишь несколько экспертов.",
    "This file only lets a chat model see images (mmproj). "
    "Choose the model file itself.":
        "Этот файл только помогает чат-модели видеть картинки (mmproj). Выберите сам файл модели.",
    "The downloaded file is damaged. Try downloading it again.":
        "Скачанный файл повреждён. Попробуйте скачать его ещё раз.",
    "Chat": "Чат",
    "remembers {count}K tokens of the conversation": "помнит {count} тыс. токенов разговора",
    "sees images": "видит картинки",
    # --- chat ---------------------------------------------------------------------------
    "Not enough memory for this chat model. Close other programs, choose a shorter "
    "conversation memory or a smaller model.":
        "Не хватает памяти для этой модели. Закройте другие программы, уменьшите память разговора "
        "или выберите модель поменьше.",
    "The chat model could not be loaded. Its file may be damaged — delete it on the "
    "Models page and download it again.":
        "Не удалось загрузить модель. Возможно, файл повреждён — удалите её на странице «Модели» "
        "и скачайте заново.",
    "This version of the chat engine cannot run this model.":
        "Эта версия движка чата не умеет запускать такую модель.",
    "The chat model took too long to load. Try again or choose a smaller model.":
        "Модель загружалась слишком долго. Попробуйте ещё раз или выберите модель поменьше.",
    "The chat engine stopped unexpectedly. Send the message again — it will restart. "
    "Details are in the log.":
        "Движок чата неожиданно остановился. Отправьте сообщение ещё раз — он перезапустится. "
        "Подробности — в журнале.",
    "The conversation no longer fits in the model's memory. Start a new chat or "
    "choose a longer memory in the chat settings.":
        "Разговор больше не помещается в память модели. Начните новый чат или увеличьте память "
        "разговора в настройках чата.",
    "Assistant": "Помощник",
    "Image prompt writer": "Промпты для картинок",
    "Video director": "Режиссёр видео",
    "Screenwriter": "Сценарист",
    "Translator": "Переводчик",
    "Text for voice-over": "Текст для озвучки",
    "New chat": "Новый чат",
    "Search chats": "Поиск по чатам",
    "Chats": "Чаты",
    "Your conversations will be listed here.": "Здесь появятся ваши разговоры.",
    "Role": "Роль",
    "Chat settings": "Настройки чата",
    "Your own instruction for this chat, instead of the role. "
    "For example: answer briefly, as a film critic.":
        "Своя инструкция для этого чата вместо роли. Например: отвечай коротко, как кинокритик.",
    "What shall we talk about?": "О чём поговорим?",
    "Everything stays on this computer. Pick a role above — or just start typing.":
        "Всё остаётся на этом компьютере. Выберите роль вверху — или просто начните писать.",
    "Come up with a plot for a 30-second video about a lighthouse":
        "Придумай сюжет 30-секундного ролика о маяке",
    "Write an image prompt: a cozy reading nook in the rain":
        "Напиши промпт для картинки: уютный уголок для чтения в дождь",
    "Explain in simple words how a neural network draws pictures":
        "Объясни простыми словами, как нейросеть рисует картинки",
    "Cancel": "Отмена",
    "Message… (Ctrl+Enter — send)": "Сообщение… (Ctrl+Enter — отправить)",
    "Message": "Сообщение",
    "Delete chat": "Удалить чат",
    "Delete “{title}”? This cannot be undone.": "Удалить «{title}»? Это нельзя отменить.",
    "The first {count} messages no longer fit in the model's memory — it does not see them. "
    "Start a new chat or choose a longer memory.":
        "Первые сообщения ({count}) больше не помещаются в память модели — она их не видит. "
        "Начните новый чат или увеличьте память разговора.",
    "Send": "Отправить",
    "~{used} / {total} tokens": "~{used} / {total} токенов",
    "Creativity": "Творческая свобода",
    "Lower — precise and repeatable, higher — more varied.":
        "Меньше — точнее и предсказуемее, больше — разнообразнее.",
    "Conversation memory": "Память разговора",
    "Longer memory needs more video memory.": "Чем длиннее память, тем больше нужно видеопамяти.",
    "Instruction": "Инструкция",
    "Editing a message: the answers after it will be replaced.":
        "Правка сообщения: ответы после него будут заменены.",
    "Today": "Сегодня",
    "Stop": "Остановить",
    "Answering in another chat…": "Модель отвечает в другом чате…",
    "No chat models yet: add one on the Models page.": "Чат-моделей пока нет: добавьте модель на странице «Модели».",
    "Chat is not available for this computer yet.": "Для этого компьютера чат пока недоступен.",
    "Yesterday": "Вчера",
    "Earlier": "Ранее",
    "Copied": "Скопировано",
    "Writing…": "Пишет…",
    "Auto": "Авто",
    "Reasoning": "Рассуждения",
    "Copy": "Копировать",
    "Thinking…": "Думает…",
    "The answer was cut short.": "Ответ прерван.",
    "{speed:.0f} tokens/s": "{speed:.0f} ток/с",
    "The model no longer sees this message: the conversation is longer than its memory.":
        "Модель больше не видит это сообщение: разговор длиннее её памяти.",
    "Edit and send again": "Изменить и отправить заново",
    "Answer again": "Ответить заново",
    "As the model's authors recommend": "Как советуют авторы модели",
    "Think before answering": "Рассуждать перед ответом",
    "The model reasons first: answers are more careful but take several times longer. "
    "The reasoning is shown folded above the answer.":
        "Модель сначала рассуждает: ответы продуманнее, но в несколько раз дольше. "
        "Рассуждения видны свёрнутыми над ответом.",
    # --- chat attachments ---------------------------------------------------------------
    "“{name}” cannot be attached. Pictures, text and code, PDF, Word and video "
    "files are supported.":
        "«{name}» нельзя приложить. Подходят картинки, текст и код, PDF, Word и видео.",
    "“{name}” could not be read. The file may be damaged.":
        "Не удалось прочитать «{name}». Возможно, файл повреждён.",
    "There is no text in “{name}”. If it is a scan, attach it as a picture.":
        "В «{name}» нет текста. Если это скан, приложите его как картинку.",
    "Reading PDF and Word files needs a component Tvorka does not have yet. "
    "Reinstall Tvorka from the latest release, or copy the text into the message.":
        "Для чтения PDF и Word нужен компонент, которого у Tvorka пока нет. Переустановите Tvorka "
        "из свежего выпуска или скопируйте текст в сообщение.",
    "Attach files: pictures, text, PDF, Word, video. "
    "You can also drag them here or paste with Ctrl+V.":
        "Приложить файлы: картинки, текст, PDF, Word, видео. Можно также перетащить их сюда "
        "или вставить через Ctrl+V.",
    "Attach files": "Приложить файлы",
    "Pasted picture": "Вставленная картинка",
    "This model does not see pictures. Choose a model marked “sees images” "
    "or remove the pictures.":
        "Эта модель не видит картинки. Выберите модель с пометкой «видит картинки» или уберите их.",
    "Reading the files…": "Читаем файлы…",
    "~{count} tokens": "~{count} ток.",
    "Remove": "Убрать",
    "reading…": "читаем…",
    "{count} frames": "кадров: {count}",
    "cut": "обрезано",
    # --- speech recognition -------------------------------------------------------------
    "There is no sound in this file.": "В этом файле нет звука.",
    "The sound could not be read. The file may be damaged.":
        "Не удалось прочитать звук. Возможно, файл повреждён.",
    "To understand “{name}”, Tvorka needs a speech recognition model. Download Whisper "
    "on the Models page (Speech recognition).":
        "Чтобы понять «{name}», Tvorka нужна модель распознавания речи. Скачайте Whisper на странице "
        "«Модели» (раздел «Распознавание речи»).",
    "No speech was found in “{name}”.": "В «{name}» не найдено речи.",
    "Speech recognition": "Распознавание речи",
    "The microphone could not be used: {error}": "Не удалось включить микрофон: {error}",
    "Voice input needs a speech recognition model. Download one on the Models page "
    "(Speech recognition): Whisper small suits most computers.":
        "Для голосового ввода нужна модель распознавания речи. Скачайте её на странице «Модели» "
        "(раздел «Распознавание речи»): Whisper small подойдёт большинству компьютеров.",
    "Recognizing…": "Распознаём…",
    "No speech was heard. Speak a little louder or closer to the microphone.":
        "Речь не слышна. Говорите чуть громче или ближе к микрофону.",
    "Dictate: press, speak, press again — the text appears here":
        "Надиктовать: нажмите, говорите, нажмите ещё раз — текст появится здесь",
    "Stop and turn the speech into text": "Остановить и превратить речь в текст",
    "Recognizing speech…": "Распознаём речь…",
    "No microphone found. Connect one and allow Windows to use it "
    "(Settings → Privacy → Microphone).":
        "Микрофон не найден. Подключите его и разрешите Windows его использовать "
        "(Параметры → Конфиденциальность → Микрофон).",
    # --- video memory -------------------------------------------------------------------
    "Stop the chat model and free memory": "Остановить чат-модель и освободить память",
    "Chat: {name}": "Чат: {name}",
    # --- passing work between sections -------------------------------------------------
    "No section can take this yet.": "Это пока некуда отправить.",
    "Ask about it in the chat": "Спросить в чате",
    "Discuss in the chat": "Обсудить в чате",
    "Send to…": "Отправить в…",
    "Made from: {kind} “{prompt}”": "Создано из: {kind} «{prompt}»",
    "Made from a chat answer": "Создано из ответа в чате",
    "Use as a reference": "Использовать как референс",
    "Draw this": "Нарисовать",
    "Prompt variants": "Варианты промпта",
    "Continue the clip: its last frame starts a new one":
        "Продолжить ролик: его последний кадр станет первым кадром нового",
    "This frame to the Image page as a reference": "Этот кадр — референсом на страницу «Изображение»",
    "Adding the voice-over…": "Накладываем озвучку…",
    "Make a video from it": "Сделать из неё видео",
    "Continue the clip": "Продолжить ролик",
    "Make a video of this": "Сделать видео",
    "Lay over the current clip": "Наложить на текущий ролик",
    "The voice-over could not be added: {error}": "Не удалось наложить озвучку: {error}",
    "Drag the picture to another section or out of Tvorka":
        "Перетащите картинку в другой раздел или за пределы Tvorka",
    "Send to… (draw it, make a video, read aloud)": "Отправить в… (нарисовать, сделать видео, озвучить)",
    # --- the chat model as a helper ------------------------------------------------------
    "The prompt could not be translated; it goes as written.":
        "Промпт не удалось перевести — он уходит как написан.",
    "Translating the prompt into English…": "Переводим промпт на английский…",
    "Improve": "Улучшить",
    "The chat model rewrites the prompt: more detail, in the wording this model understands best":
        "Чат-модель перепишет промпт: больше деталей, в той форме, которую эта модель понимает лучше всего",
    "To English": "На английский",
    "Most image models understand English best": "Большинство моделей изображений лучше понимают английский",
    "Suggest what must not appear in the picture": "Предложить, чего не должно быть на картинке",
    "From the picture": "По картинке",
    "The chat model describes the reference as a prompt": "Чат-модель опишет референс как промпт",
    "Check the result": "Оценить и улучшить",
    "The chat model compares the picture with the prompt and suggests a better one":
        "Чат-модель сравнит картинку с промптом и предложит промпт лучше",
    "Improved prompt": "Улучшенный промпт",
    "Translation": "Перевод",
    "Translate": "Перевести",
    "Translate the text into the selected voice's language": "Перевести текст на язык выбранного голоса",
    "Describe the video": "Описать видео",
    "Write narration for the video": "Написать текст за кадром",
    "Describe what happens in the attached video in chronological order. Reply with text only and do not call tools.":
        "Опиши, что происходит в приложенном видео, в хронологическом порядке. Ответь текстом без вызова инструментов.",
    "Write a short narration script for the attached video, following the action. "
    "Reply with the script only and do not call tools.":
        "Напиши короткий закадровый текст по событиям приложенного видео. Верни только текст без вызова инструментов.",
    "Prompt from the picture": "Промпт по картинке",
    "Translate prompts into English before creating": "Переводить промпт на английский перед созданием",
    "Image and video models understand English best. Write in any language — "
    "the chat model translates the prompt (the original stays in the field).":
        "Модели изображений и видео лучше понимают английский. Пишите на любом языке — чат-модель "
        "переведёт промпт (в поле останется ваш текст).",
    "Prepare the text": "Подготовить текст",
    "The chat model writes numbers and abbreviations out in words, fixes punctuation and the letter ё "
    "— for a clean reading":
        "Чат-модель распишет числа и сокращения словами, поправит пунктуацию и букву ё — чтобы прочитать "
        "чисто",
    "Text ready for reading": "Текст для чтения",
    "The chat model turns the idea into one shot: what moves, how the camera goes, the light":
        "Чат-модель превратит идею в один план: что движется, как идёт камера, какой свет",
    "Most video models understand English best": "Большинство видеомоделей лучше понимают английский",
    "Proposal": "Предложение",
    "Apply": "Применить",
    "The chat model is working on it…": "Чат-модель работает…",
    "This needs a chat model. Download one on the Models page (Chat) — Qwen3.5 4B suits most "
    "computers.":
        "Для этого нужна чат-модель. Скачайте её на странице «Модели» (раздел «Чат») — Qwen3.5 4B "
        "подойдёт большинству компьютеров.",
    "This needs a chat model that sees images, with its image file downloaded.":
        "Для этого нужна чат-модель, которая видит картинки, — вместе с её файлом для картинок.",
    "The chat model gave an empty answer. Try again.": "Чат-модель ответила пустотой. Попробуйте ещё раз.",
    # --- tools in the chat ---------------------------------------------------------------
    "The model may suggest creating a picture, a video clip or a voice-over":
        "Модель может предлагать создать картинку, видео или озвучку",
    "It shows a card under its answer; nothing is created until you press “Create”.":
        "Под ответом появится карточка; ничего не создаётся, пока вы не нажмёте «Создать».",
    "The model suggests creating a picture": "Модель предлагает создать картинку",
    "The model suggests creating a video clip": "Модель предлагает создать видео",
    "The model suggests reading this aloud": "Модель предлагает озвучить текст",
    "Edit first": "Сначала изменить",
    "Open the section": "Открыть раздел",
    "Being created…": "Создаётся…",
    "Cancelled.": "Отменено.",
    "Handed over to the section to edit.": "Передано в раздел для правки.",
    "The model made a broken request. Ask again in other words.":
        "Модель ошиблась в запросе. Попросите ещё раз другими словами.",
    # --- video from an idea ---------------------------------------------------------------
    "Video from an idea": "Ролик из идеи",
    "Describe a short video or dictate your idea.": "Опишите короткий ролик или надиктуйте идею.",
    "Video idea": "Идея ролика",
    "Number of scenes": "Число сцен",
    "Russian narration": "Озвучка на русском",
    "English narration": "Озвучка на английском",
    "Draft storyboard": "Составить раскадровку",
    "Storyboard": "Раскадровка",
    "Image prompt": "Описание кадра",
    "Motion": "Движение",
    "Narration": "Текст за кадром",
    "Move scene up": "Сцену выше",
    "Move scene down": "Сцену ниже",
    "Remove scene": "Удалить сцену",
    "Image model": "Модель для кадров",
    "Image-to-video model": "Модель для оживления кадров",
    "Voice model": "Модель озвучки",
    "Assemble video": "Собрать ролик",
    "Open Gallery": "Открыть галерею",
    "No compatible model installed": "Совместимая модель не установлена",
    "Install a compatible local image, image-to-video or voice model on the Models page.":
        "Установите недостающие модели на странице «Модели».",
    "Finish dictation first.": "Сначала завершите диктовку.",
    "Drafting the storyboard…": "Составляем раскадровку…",
    "The storyboard was incomplete. Try drafting it again.":
        "Модель вернула неполную раскадровку. Попробуйте составить её ещё раз.",
    "Review the scenes, then assemble the video.": "Проверьте сцены и нажмите «Собрать ролик».",
    "Install a local chat model on the Models page to draft the storyboard.":
        "Для раскадровки установите локальную чат-модель на странице «Модели».",
    "The video is ready in the Gallery.": "Ролик готов и добавлен в галерею.",
    "Made from an idea in Chat": "Собрано из идеи в «Чате»",
    "GGUF image and video models need the CUDA dependencies of Tvorka. Reinstall the CUDA build of the app.":
        "Для моделей GGUF нужны зависимости Tvorka для CUDA. Переустановите сборку приложения с CUDA.",
    "This GGUF model needs an NVIDIA graphics card with native BF16 and a CUDA build.":
        "Этой модели GGUF нужна видеокарта NVIDIA с аппаратной поддержкой BF16 и сборка с CUDA.",
    "The GGUF transformer and 4-bit text encoder are moved to the graphics card one at a time.":
        "GGUF-трансформер и 4-битный текстовый энкодер загружаются на видеокарту по очереди.",
    # --- coding workspace ---------------------------------------------------------------
    "Agent": "Агент",
    "Allow in this session": "Разрешить в этой сессии",
    "Applied {path}": "Применено: {path}",
    "Applies text edits in this session. Deletion always asks.":
        "Применяет текстовые правки в этой сессии. Удаление требует подтверждения.",
    "Ask the model to fix the edit": "Попросить модель исправить правку",
    "Auto · {size}K": "Авто · {size} тыс.",
    "Auto-apply": "Автоправки",
    "Auto-apply in this session": "Применять в этой сессии",
    "Changes": "Изменения",
    "Code": "Код",
    "Code can change files in this project. Approved shell commands run with your account permissions. "
    "Choose a project folder you trust.":
        "Вкладка «Код» может менять файлы проекта. Подтверждённые команды запускаются с правами вашей "
        "учётной записи. Выбирайте папку проекта, которой доверяете.",
    "Code model": "Модель для кода",
    "Coding task": "Задача для модели",
    "Command output": "Вывод команды",
    "Command requires careful review": "Проверьте команду перед запуском",
    "Context length": "Размер контекста",
    "Create image asset": "Создать изображение для проекта",
    "Decline": "Отклонить",
    "Delete file": "Удалить файл",
    "Describe a coding task or ask about this project…": "Опишите задачу или задайте вопрос о проекте…",
    "Earlier messages were summarized.": "Начало разговора сжато в сводку.",
    "Edits": "Правки",
    "Edits reverted.": "Правки отменены.",
    "Empty project": "Пустой проект",
    "Fix the proposed change to {path}. The earlier edit failed: {reason}":
        "Исправь предложенную правку в {path}. Предыдущая правка не удалась: {reason}",
    "Git status": "Статус Git",
    "Got it": "Понятно",
    "Install a chat model": "Установите чат-модель",
    "Install a local chat model and its engine on the Models page.":
        "Установите локальную чат-модель и её движок на странице «Модели».",
    "List project files": "Список файлов проекта",
    "My project": "Мой проект",
    "New project": "Новый проект",
    "No applied edits yet.": "Применённых правок пока нет.",
    "No changes reported by Git.": "Git не сообщил об изменениях.",
    "No text editor could be found.": "Не удалось найти текстовый редактор.",
    "Open a project to edit files, ask about code or run a local check.":
        "Откройте проект, чтобы редактировать файлы, задавать вопросы о коде и запускать проверки.",
    "Open folder": "Открыть папку",
    "Open in Code": "Открыть во вкладке «Код»",
    "Open in browser": "Открыть в браузере",
    "Open in editor": "Открыть в редакторе",
    "Optional reason for declining": "Причина отклонения (необязательно)",
    "Output": "Вывод",
    "Project": "Проект",
    "Project files": "Файлы проекта",
    "Project name": "Название проекта",
    "Proposed change": "Предложенная правка",
    "Python script": "Скрипт Python",
    "Question": "Вопрос",
    "Recent projects": "Недавние проекты",
    "Read file": "Чтение файла",
    "Run command": "Запустить команду",
    "Run this command?": "Запустить эту команду?",
    "Search project": "Поиск по проекту",
    "Small models may struggle with multi-step tasks. Try Edits for targeted changes.":
        "Небольшим моделям сложнее выполнять многошаговые задачи. Для точечных изменений попробуйте «Правки».",
    "Task finished.": "Задача завершена.",
    "Template": "Шаблон",
    "The coding model uses {size}K tokens of context.": "Контекст модели — {size} тыс. токенов.",
    "The model reached 30 steps. Send a message to continue.":
        "Модель выполнила 30 шагов. Отправьте сообщение, чтобы продолжить.",
    "The model repeated the same action and stopped.": "Модель повторила одно и то же действие и остановилась.",
    "The task and selected files exceed the context. Select fewer files or a longer context.":
        "Задача и файлы превышают контекст. Выберите меньше файлов или увеличьте контекст.",
    "This model supports the Edits mode. Agent and Question need tool support.":
        "Доступен режим «Правки». Для режимов «Агент» и «Вопрос» нужна поддержка инструментов.",
    "Timeout: {seconds} s": "Лимит времени: {seconds} с",
    "Try a short script, a small web page or a focused change in a few files.":
        "Попробуйте короткий скрипт, небольшую веб-страницу или точечную правку в нескольких файлах.",
    "Undo history": "История правок",
    "Undo last edit": "Откатить шаг",
    "Undo this edit and every later edit.": "Откатить эту правку и все более поздние.",
    "Web page": "Веб-страница",
    "Working on the project…": "Работаем над проектом…",
    "{size}K tokens": "{size} тыс. токенов",
}
