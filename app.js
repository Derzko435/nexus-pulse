/* NEXUS PULSE — интерактив портала */

/** Единственное место для Discord-инвайта. Пусто / "#" → кнопки в состоянии «Скоро». */
const DISCORD_INVITE_URL = "https://discord.gg/7JvfzNrt4x";

(function () {
  "use strict";

  /* ---------- Данные каталога (статичные) ---------- */
  const GAMES = [
    { id: "cp2077", title: "Cyberpunk 2077", genre: "RPG", rating: 9.1, platforms: ["PC", "PS5", "Xbox"], desc: "Найт-Сити, импланты и выборы, которые ломают сюжет.", color: ["#1a3a4a", "#4a1040"], demand: 1.2 },
    { id: "elden", title: "Elden Ring", genre: "RPG", rating: 9.6, platforms: ["PC", "PS5", "Xbox"], desc: "Открытый мир FromSoftware — боль красивая и заслуженная.", color: ["#2a2010", "#4a3010"], demand: 1.15 },
    { id: "bg3", title: "Baldur's Gate 3", genre: "RPG", rating: 9.7, platforms: ["PC", "PS5"], desc: "CRPG года: компаньоны, кубики и immaculate storytelling.", color: ["#1a2040", "#3a1050"], demand: 1.05 },
    { id: "witcher3", title: "The Witcher 3", genre: "RPG", rating: 9.5, platforms: ["PC", "PS5", "Xbox", "Switch"], desc: "Геральт, чудовища и квесты, которые до сих пор эталон.", color: ["#102030", "#204040"], demand: 0.85 },
    { id: "rdr2", title: "Red Dead Redemption 2", genre: "RPG", rating: 9.6, platforms: ["PC", "PS5", "Xbox"], desc: "Эпический вестерн Rockstar с живым миром.", color: ["#201810", "#382818"], demand: 1.25 },
    { id: "gtav", title: "GTA V / Online", genre: "экшен", rating: 9.0, platforms: ["PC", "PS5", "Xbox"], desc: "Лос-Сантос живёт уже больше десятилетия.", color: ["#102828", "#184040"], demand: 1.0 },
    { id: "skyrim", title: "The Elder Scrolls V: Skyrim", genre: "RPG", rating: 9.3, platforms: ["PC", "PS5", "Xbox", "Switch"], desc: "Драконы, моды и ещё один «последний» забег.", color: ["#1a2838", "#304858"], demand: 0.7 },
    { id: "ffxiv", title: "Final Fantasy XIV", genre: "MMO", rating: 9.2, platforms: ["PC", "PS5"], desc: "MMORPG, где сюжет реально хочется пройти.", color: ["#201830", "#382850"], demand: 0.85 },
    { id: "wukong", title: "Black Myth: Wukong", genre: "экшен", rating: 8.9, platforms: ["PC", "PS5"], desc: "Боевая поэма по Journey to the West.", color: ["#301808", "#502010"], demand: 1.3 },
    { id: "persona5", title: "Persona 5 Royal", genre: "RPG", rating: 9.5, platforms: ["PC", "PS5", "Xbox", "Switch"], desc: "Стиль, джаз и лучшие подземелья Atlus.", color: ["#300810", "#501020"], demand: 0.75 },
    { id: "diablo4", title: "Diablo IV", genre: "RPG", rating: 8.2, platforms: ["PC", "PS5", "Xbox"], desc: "Тёмный лутер с сезонным эндгеймом.", color: ["#200810", "#401018"], demand: 1.1 },
    { id: "poe2", title: "Path of Exile 2", genre: "RPG", rating: 8.8, platforms: ["PC", "PS5"], desc: "Хардкорный ARPG с бездонным билдингом.", color: ["#181020", "#301830"], demand: 1.05 },
    { id: "cs2", title: "Counter-Strike 2", genre: "киберспорт", rating: 8.4, platforms: ["PC"], desc: "Классика тактического шутера. Ранкид не спит.", color: ["#1a3010", "#304010"], demand: 0.7 },
    { id: "valorant", title: "Valorant", genre: "киберспорт", rating: 8.6, platforms: ["PC"], desc: "Агенты, способности и headshot-мета Riot.", color: ["#301020", "#501030"], demand: 0.75 },
    { id: "dota2", title: "Dota 2", genre: "киберспорт", rating: 9.0, platforms: ["PC"], desc: "MOBA без потолка скилла. The International ждёт.", color: ["#201010", "#401820"], demand: 0.8 },
    { id: "lol", title: "League of Legends", genre: "киберспорт", rating: 8.3, platforms: ["PC"], desc: "Самая смотрибельная сцена и вечный «ещё один кат».", color: ["#101830", "#182050"], demand: 0.65 },
    { id: "rocket", title: "Rocket League", genre: "киберспорт", rating: 8.7, platforms: ["PC", "PS5", "Xbox", "Switch"], desc: "Футбол на машинах — проще войти, сложнее выйти.", color: ["#102848", "#184868"], demand: 0.55 },
    { id: "r6", title: "Rainbow Six Siege", genre: "киберспорт", rating: 8.7, platforms: ["PC", "PS5", "Xbox"], desc: "Разрушаемые карты и операторы с гаджетами.", color: ["#181820", "#282838"], demand: 0.88 },
    { id: "fortnite", title: "Fortnite", genre: "киберспорт", rating: 8.0, platforms: ["PC", "PS5", "Xbox", "Switch", "Mobile"], desc: "Батл-рояль, коллабы и строительная мета.", color: ["#102040", "#203060"], demand: 0.7 },
    { id: "apex", title: "Apex Legends", genre: "FPS", rating: 8.5, platforms: ["PC", "PS5", "Xbox"], desc: "Бригады, движение и легенды с уникальными ультами.", color: ["#301818", "#502020"], demand: 0.95 },
    { id: "ow2", title: "Overwatch 2", genre: "FPS", rating: 7.8, platforms: ["PC", "PS5", "Xbox"], desc: "Геройский шутер: роли, ульты, командные драки.", color: ["#203040", "#304860"], demand: 0.9 },
    { id: "doom", title: "DOOM Eternal", genre: "FPS", rating: 9.0, platforms: ["PC", "PS5", "Xbox"], desc: "Рип энд тир. Саундтрек рвёт потолок.", color: ["#301008", "#501010"], demand: 1.0 },
    { id: "halo", title: "Halo Infinite", genre: "FPS", rating: 8.1, platforms: ["PC", "Xbox"], desc: "Мастер Чиф, открытый мир и классический мультиплеер.", color: ["#182838", "#284858"], demand: 0.9 },
    { id: "codmw", title: "Call of Duty: Modern Warfare III", genre: "FPS", rating: 7.6, platforms: ["PC", "PS5", "Xbox"], desc: "Быстрый паб и Warzone в одной экосистеме.", color: ["#201818", "#382828"], demand: 1.15 },
    { id: "destiny2", title: "Destiny 2", genre: "FPS", rating: 8.3, platforms: ["PC", "PS5", "Xbox"], desc: "Лутер-шутер с рейдами и сезонными ивентами.", color: ["#101828", "#182848"], demand: 0.95 },
    { id: "titanfall2", title: "Titanfall 2", genre: "FPS", rating: 9.1, platforms: ["PC", "PS5", "Xbox"], desc: "Лучшая кампания шутера + движение мечты.", color: ["#181820", "#302828"], demand: 0.85 },
    { id: "ultrakill", title: "ULTRAKILL", genre: "FPS", rating: 9.2, platforms: ["PC"], desc: "Буст-фанк шутер, где стиль — это урон.", color: ["#300808", "#501010"], demand: 0.6 },
    { id: "civ6", title: "Civilization VI", genre: "стратегия", rating: 8.8, platforms: ["PC", "Switch"], desc: "Ещё один ход — и вот уже 3 часа ночи.", color: ["#102838", "#184050"], demand: 0.6 },
    { id: "aoe4", title: "Age of Empires IV", genre: "стратегия", rating: 8.4, platforms: ["PC", "Xbox"], desc: "Классика RTS с современным нетом и кампаниями.", color: ["#282010", "#403018"], demand: 0.75 },
    { id: "xcom2", title: "XCOM 2", genre: "стратегия", rating: 9.1, platforms: ["PC", "PS5", "Xbox"], desc: "Тактика, где плохое решение = мёртвый солдат.", color: ["#102018", "#183028"], demand: 0.7 },
    { id: "totalwar", title: "Total War: Warhammer III", genre: "стратегия", rating: 8.6, platforms: ["PC"], desc: "Гранд-кампания + битвы тысяч юнитов.", color: ["#281818", "#402020"], demand: 1.1 },
    { id: "ck3", title: "Crusader Kings III", genre: "стратегия", rating: 9.0, platforms: ["PC", "PS5", "Xbox"], desc: "Драмы двора, интриги и мемные династии.", color: ["#201018", "#381828"], demand: 0.65 },
    { id: "stellaris", title: "Stellaris", genre: "стратегия", rating: 8.5, platforms: ["PC", "PS5", "Xbox"], desc: "4X в космосе: империи, кризисы, ассимиляция.", color: ["#081028", "#102048"], demand: 0.7 },
    { id: "hoi4", title: "Hearts of Iron IV", genre: "стратегия", rating: 8.4, platforms: ["PC"], desc: "Глобальная WWII-стратегия для маньяков фронтов.", color: ["#181010", "#301818"], demand: 0.6 },
    { id: "rimworld", title: "RimWorld", genre: "стратегия", rating: 9.3, platforms: ["PC"], desc: "Колония на краю галактики и генератор историй.", color: ["#182010", "#283018"], demand: 0.5 },
    { id: "hollow", title: "Hollow Knight", genre: "инди", rating: 9.4, platforms: ["PC", "Switch", "PS5"], desc: "Метроидвания с атмосферой и боссами мечты.", color: ["#101020", "#181838"], demand: 0.45 },
    { id: "hades", title: "Hades", genre: "инди", rating: 9.3, platforms: ["PC", "Switch", "PS5", "Xbox"], desc: "Рогалик, где каждый побег — история.", color: ["#301010", "#501818"], demand: 0.55 },
    { id: "celeste", title: "Celeste", genre: "инди", rating: 9.2, platforms: ["PC", "Switch", "PS5", "Xbox"], desc: "Платформер про гору, тревогу и assist-режим.", color: ["#201838", "#382850"], demand: 0.4 },
    { id: "stardew", title: "Stardew Valley", genre: "инди", rating: 9.5, platforms: ["PC", "Switch", "PS5", "Xbox", "Mobile"], desc: "Ферма, друзья и бесконечный уют.", color: ["#183018", "#284028"], demand: 0.35 },
    { id: "hades2", title: "Hades II", genre: "инди", rating: 9.1, platforms: ["PC"], desc: "Мелиноя против Кроноса — рогалик нового витка.", color: ["#201028", "#381840"], demand: 0.6 },
    { id: "balatro", title: "Balatro", genre: "инди", rating: 9.0, platforms: ["PC", "Switch", "PS5", "Xbox", "Mobile"], desc: "Покерный рогалик, от которого сложно оторваться.", color: ["#201010", "#401820"], demand: 0.3 },
    { id: "vampire", title: "Vampire Survivors", genre: "инди", rating: 8.8, platforms: ["PC", "Switch", "PS5", "Xbox", "Mobile"], desc: "Один экран, сто врагов, чистый дофамин.", color: ["#180820", "#300830"], demand: 0.25 },
    { id: "outerwilds", title: "Outer Wilds", genre: "инди", rating: 9.4, platforms: ["PC", "PS5", "Xbox"], desc: "Исследование, тайны и 22-минутный цикл.", color: ["#101828", "#182840"], demand: 0.45 },
    { id: "re4", title: "Resident Evil 4 Remake", genre: "хоррор", rating: 9.3, platforms: ["PC", "PS5", "Xbox"], desc: "Римейк легенды — напряжение и идеальный геймплей.", color: ["#180808", "#300810"], demand: 0.95 },
    { id: "reVillage", title: "Resident Evil Village", genre: "хоррор", rating: 8.7, platforms: ["PC", "PS5", "Xbox"], desc: "Замок, деревня и вампирская опера.", color: ["#100810", "#281018"], demand: 0.9 },
    { id: "alanwake2", title: "Alan Wake 2", genre: "хоррор", rating: 9.0, platforms: ["PC", "PS5", "Xbox"], desc: "Нарративный хоррор про свет, тьму и рукопись.", color: ["#081018", "#101830"], demand: 1.05 },
    { id: "phasmo", title: "Phasmophobia", genre: "хоррор", rating: 8.5, platforms: ["PC", "PS5", "Xbox"], desc: "Кооп-охота на призраков с микрофоном и криками.", color: ["#101018", "#201828"], demand: 0.55 },
    { id: "outlast", title: "Outlast Trials", genre: "хоррор", rating: 8.2, platforms: ["PC", "PS5", "Xbox"], desc: "Кооп-испытания в сумасшедшей клинике.", color: ["#180808", "#280810"], demand: 0.7 },
    { id: "deadspace", title: "Dead Space Remake", genre: "хоррор", rating: 9.1, platforms: ["PC", "PS5", "Xbox"], desc: "Космос, некроморфы и плазменный резак.", color: ["#101010", "#282018"], demand: 1.0 },
    { id: "lethal", title: "Lethal Company", genre: "хоррор", rating: 8.6, platforms: ["PC"], desc: "Кооп-хоррор про квоты, лут и друзей-предателей.", color: ["#181808", "#302810"], demand: 0.4 },
    { id: "forza5", title: "Forza Horizon 5", genre: "гонки", rating: 9.2, platforms: ["PC", "Xbox"], desc: "Открытый мир Мексики и лучший аркадный драйв.", color: ["#201808", "#403010"], demand: 0.95 },
    { id: "gt7", title: "Gran Turismo 7", genre: "гонки", rating: 8.8, platforms: ["PS5"], desc: "Симулятор мечты для владельцев DualSense.", color: ["#101820", "#182838"], demand: 0.9 },
    { id: "f1_24", title: "F1 24", genre: "гонки", rating: 8.3, platforms: ["PC", "PS5", "Xbox"], desc: "Официальная Формула-1 с карьерой и онлайном.", color: ["#200808", "#400810"], demand: 0.85 },
    { id: "dirt", title: "DiRT Rally 2.0", genre: "гонки", rating: 8.7, platforms: ["PC", "PS5", "Xbox"], desc: "Жёсткий ралли-сим — одна ошибка и ты в кювете.", color: ["#181410", "#302418"], demand: 0.7 },
    { id: "nfs", title: "Need for Speed Unbound", genre: "гонки", rating: 7.9, platforms: ["PC", "PS5", "Xbox"], desc: "Уличные гонки с арт-стилем и тюнингом.", color: ["#101028", "#281850"], demand: 0.85 },
    { id: "assetto", title: "Assetto Corsa Competizione", genre: "гонки", rating: 8.9, platforms: ["PC", "PS5", "Xbox"], desc: "GT-сим для рулей и телеметрии.", color: ["#101018", "#202028"], demand: 0.8 },
    { id: "msfs", title: "Microsoft Flight Simulator", genre: "симуляторы", rating: 9.0, platforms: ["PC", "Xbox"], desc: "Вся планета как песочница для пилотов.", color: ["#082038", "#103858"], demand: 1.4 },
    { id: "ets2", title: "Euro Truck Simulator 2", genre: "симуляторы", rating: 8.9, platforms: ["PC"], desc: "Дорога, подкасты и медитативный вайб.", color: ["#182018", "#283028"], demand: 0.5 },
    { id: "farming", title: "Farming Simulator 25", genre: "симуляторы", rating: 8.0, platforms: ["PC", "PS5", "Xbox"], desc: "Техника, поля и кооператив на ферме.", color: ["#203010", "#304818"], demand: 0.65 },
    { id: "cities", title: "Cities: Skylines II", genre: "симуляторы", rating: 7.8, platforms: ["PC", "PS5", "Xbox"], desc: "Градостроитель нового поколения.", color: ["#102830", "#184050"], demand: 1.1 },
    { id: "ibeam", title: "BeamNG.drive", genre: "симуляторы", rating: 9.1, platforms: ["PC"], desc: "Физика повреждений, от которой аж больно.", color: ["#201808", "#382818"], demand: 0.75 },
    { id: "snowrunner", title: "SnowRunner", genre: "симуляторы", rating: 8.6, platforms: ["PC", "PS5", "Xbox"], desc: "Грязь, лебёдки и оффроуд-логистика.", color: ["#181410", "#2a2418"], demand: 0.7 },
    { id: "gow", title: "God of War Ragnarök", genre: "экшен", rating: 9.4, platforms: ["PC", "PS5"], desc: "Кратос, Атрей и финал нордической саги.", color: ["#101820", "#203040"], demand: 1.05 },
    { id: "spiderman2", title: "Marvel's Spider-Man 2", genre: "экшен", rating: 9.0, platforms: ["PS5"], desc: "Два Питера, Веном и лучший свинг.", color: ["#200810", "#401020"], demand: 1.0 },
    { id: "totk", title: "Zelda: Tears of the Kingdom", genre: "экшен", rating: 9.6, platforms: ["Switch"], desc: "Строй, летай, ломай физику Хайрула.", color: ["#183020", "#284838"], demand: 0.7 },
    { id: "sekiro", title: "Sekiro: Shadows Die Twice", genre: "экшен", rating: 9.4, platforms: ["PC", "PS5", "Xbox"], desc: "Парирование как религия. Смерть учит.", color: ["#201010", "#401818"], demand: 0.95 },
    { id: "mhwilds", title: "Monster Hunter Wilds", genre: "экшен", rating: 8.7, platforms: ["PC", "PS5", "Xbox"], desc: "Охота на титанов в живом мире.", color: ["#202010", "#383818"], demand: 1.2 },
    { id: "hogwarts", title: "Hogwarts Legacy", genre: "RPG", rating: 8.1, platforms: ["PC", "PS5", "Xbox", "Switch"], desc: "Открытый Хогвартс и магия кастомизации.", color: ["#181428", "#2a2040"], demand: 1.0 },
    { id: "acvalhalla", title: "Assassin's Creed Valhalla", genre: "экшен", rating: 7.9, platforms: ["PC", "PS5", "Xbox"], desc: "Викинги, рейды и огромная Англия.", color: ["#102028", "#183848"], demand: 1.05 },
    { id: "wow", title: "World of Warcraft", genre: "MMO", rating: 8.8, platforms: ["PC"], desc: "Классика MMO: рейды, мифика+, аукцион.", color: ["#201808", "#403010"], demand: 0.8 },
    { id: "gw2", title: "Guild Wars 2", genre: "MMO", rating: 8.7, platforms: ["PC"], desc: "Горизонтальный прогресс и живой мир.", color: ["#081828", "#103050"], demand: 0.7 },
    { id: "eso", title: "The Elder Scrolls Online", genre: "MMO", rating: 8.3, platforms: ["PC", "PS5", "Xbox"], desc: "Тамриель в онлайне — квесты и альянсы.", color: ["#182010", "#283020"], demand: 0.75 },
    { id: "lostark", title: "Lost Ark", genre: "MMO", rating: 7.8, platforms: ["PC"], desc: "Изометрический экшен-MMO с рейдами.", color: ["#201018", "#401828"], demand: 0.85 },
    { id: "newworld", title: "New World: Aeternum", genre: "MMO", rating: 7.5, platforms: ["PC", "PS5", "Xbox"], desc: "Крафт, войны компаний и PvP-территории.", color: ["#102018", "#183830"], demand: 0.9 },
    { id: "throne", title: "Throne and Liberty", genre: "MMO", rating: 7.6, platforms: ["PC", "PS5", "Xbox"], desc: "Масштабные осады и трансформации.", color: ["#181028", "#301840"], demand: 0.95 },
  ];


  const GUIDES = [
    { tag: "FPS · железо", title: "Как поднять FPS без новой видеокарты", time: "12 мин", text: "Драйверы, DLSS/FSR/XeSS, лимит кадров = Hz+1, закрыть Chrome/Discord overlay, правильный Power Plan." },
    { tag: "CS2", title: "Настройки графики CS2 под ранкид", time: "8 мин", text: "Низкие тени и эффекты, MSAA выкл, Boost Player Contrast вкл — стабильный FPS важнее «красоты»." },
    { tag: "Valorant", title: "Сенса и кроссхейр: быстрый старт", time: "7 мин", text: "eDPI 200–400, raw input вкл, ускорение мыши в Windows выкл. Кроссхейр — тонкий, контрастный, без обводки-шума." },
    { tag: "CS2", title: "Экономика раундов: когда форс, когда эко", time: "10 мин", text: "После проигрыша пистолетного — эко. Форс только если у тимы есть план на пики и утилиту." },
    { tag: "Valorant", title: "Ранкед-климб: утилита на атаке", time: "11 мин", text: "Один смок = один вход. Не трать вспышку «в воздух» — синхронизируй с пиком тиммейта." },
    { tag: "Dota 2", title: "Драфт для паба: герои текущего патча", time: "11 мин", text: "Бери то, что закрывает лейны и даёт спелл-иммун / сейв. Контрпик важнее «любимого» героя." },
    { tag: "LoL", title: "Как не сливать раннюю игру на миде", time: "9 мин", text: "Вард на 1:00–1:30, трек джангла, не пушь без вижена. CS > бессмысленные алл-ины." },
    { tag: "Apex", title: "Движение и позиционка в Apex", time: "10 мин", text: "Высота + третья сторона. Не лутайся под зоной: ротация раньше лута «на глаз»." },
    { tag: "R6 Siege", title: "Атака: дрон до входа", time: "8 мин", text: "Один дрон = один угол. Не входи в сайт, пока не знаешь, где роум и какой гаджет стоит." },
    { tag: "Elden Ring", title: "Боссы: как читать паттерны", time: "9 мин", text: "Учи 2–3 сейф-окна на удар, не жадничай. Spirit Ash / суммоны — легитимный инструмент, не «чит»." },
    { tag: "Sekiro", title: "Парирование вместо уклонов", time: "7 мин", text: "Звук удара > глаз. Держи posture-давление, не отходи после каждого блока — это ломает ритм." },
    { tag: "Wukong", title: "Black Myth: ресурсная экономика боя", time: "8 мин", text: "Не спамь тяжёлые заранее. Сохраняй фокус/фокус-скиллы на окна после идеальных уклонов." },
    { tag: "WoW", title: "Mythic+: чеклист перед ключом", time: "6 мин", text: "Еда, фласки, камни, ключ, маршруты с таймерами. Голос > пинги эмодзи в тяжёлых пуллах." },
    { tag: "Diablo IV", title: "Сезонный старт без слива часов", time: "10 мин", text: "Следуй leveling-маршруту до 50, не крафти всё подряд. Легендарки под билд > «красивый» лут." },
    { tag: "PoE 2", title: "Билд для первого лига-старта", time: "12 мин", text: "Бери проверенный league-starter с понятным clear. Не изобретай tree в первые 20 часов." },
    { tag: "GTA Online", title: "Экономика: как фармить без выгорания", time: "9 мин", text: "Миксируй Cayo / автошоп / VIP. Не сиди в одном реплейте 4 часа — ротация контента держит MMR настроения." },
    { tag: "Warzone", title: "Лут-маршрут и loadout", time: "8 мин", text: "Контракты > рандомный лут. Loadout бери сразу после первого удовлетворительного оружия." },
    { tag: "Fortnite", title: "Стройки для новичка в ранкеде", time: "7 мин", text: "90s и cone-peek важнее сложных туннелей. Играй zone, не хайграунд любой ценой." },
    { tag: "Rocket League", title: "Механика → ранг: что качать первым", time: "8 мин", text: "Удар по мячу и ротация > air dribble. Бесплатный гол от буста-менеджмента." },
    { tag: "Ферма / уют", title: "Stardew: чеклист первой весны", time: "6 мин", text: "Пастернак → дождь-план · рюкзак · шахты с днём 5 · не трать всё на семена клубники вслепую." },
    { tag: "Хоррор", title: "Phasmophobia: улики без паники", time: "7 мин", text: "Термо + EMF + записи. Не кричи имя сразу. Двери и шаги — твой радар, не «прыгалки»." },
    { tag: "Симуляторы", title: "ETS2: сетап для длинных рейсов", time: "5 мин", text: "Cruise control, реалистичные зеркала, подкаст/музыка. Снизь чувствительность руля — меньше усталости." },
    { tag: "Стратегии", title: "Civ 6: первые 50 ходов без фейла", time: "10 мин", text: "3–4 города к t50, eureka через руины и районы, не игнорь walls если сосед агрессивный." },
    { tag: "Стратегии", title: "XCOM 2: как не вайпнуть отряд", time: "8 мин", text: "Overwatch-цепочка, half-cover = почти смерть, всегда имей план отхода до агрессивного пуша." },
    { tag: "Периферия", title: "Мышь: DPI, polling, raw input", time: "8 мин", text: "400–1600 DPI достаточно. Отключи ускорение Windows. Polling 1000 Hz — стандарт для FPS." },
    { tag: "Периферия", title: "Клавиатура: rapid trigger и SOCD", time: "8 мин", text: "Линейные свитчи + RT дают чистый counter-strafe в CS/Valorant. Настрой actuation под палец, не «на минимум любой ценой»." },
    { tag: "Сеть", title: "Пинг и Wi-Fi: что убивает онлайн", time: "9 мин", text: "Кабель > 5 GHz. Закрой торренты, отключи буфер bloat (SQM/QoS). Смотри jitter, не только «пинг 20»." },
    { tag: "Windows", title: "10 настроек Windows под игры", time: "7 мин", text: "Game Mode вкл, Hardware GPU Scheduling, Xbox Game Bar выкл, визуальные эффекты — «обеспечить наилучшее быстродействие»." },
    { tag: "Звук", title: "Позиционирование шагов в FPS", time: "6 мин", text: "Стерео-наушники, виртуальный 7.1 часто врёт. Подними mid-high 2–6 kHz аккуратно — шаги слышнее голоса." },
    { tag: "Психология", title: "Анти-тилт после трёх поражений", time: "7 мин", text: "Тайм-аут 5 минут, вода, смена плейлиста. Правило: стоп после −2 ранга / −50 MMR за сессию." },
  ];

  const FACTS = [
    "В оригинальном Doom (1993) мышь добавили позже WASD — стандарты управления рождались на ходу.",
    "Рекордные сессии в Euro Truck Simulator 2 у стримеров измеряются сутками.",
    "Elden Ring прячет целые квестовые линии за одной фразой NPC.",
    "Самый короткий спидран Celeste с assist — секунды; без него — часы практики.",
    "В Dota 2 руны на реке появляются каждые 2 минуты — топы слышат это метрономом.",
    "Stardew Valley написал один человек — ConcernedApe — и игра всё ещё обновляется.",
    "Лайфхак: V-Sync выкл + лимит FPS через RTSS часто стабильнее «безлимита».",
    "Лайфхак: Discord overlay и браузер с 30 вкладками легко крадут 10–20 FPS.",
    "Лайфхак: в Steam «режим большой картины» делает геймпад-навигацию человеческой.",
    "Phasmophobia реагирует на голос: имя призрака повышает активность.",
    "В Forza Horizon 5 фоторежим — полноценная «камера путешествий».",
    "ULTRAKILL считает стиль комбо так же важно, как урон — score attack в крови шутера.",
  ];

  const GLOSSARY = [
    { term: "Tilt / тильт", def: "Эмоциональный перегрев после поражений: решения становятся хуже, пока не остынешь." },
    { term: "Ping / пинг", def: "Задержка туда-обратно до сервера в миллисекундах. Ниже — лучше для онлайна." },
    { term: "Smurf / смурф", def: "Опытный игрок на низком ранге на новом аккаунте." },
    { term: "Meta / мета", def: "Наиболее эффективные стратегии и пики на текущем патче." },
    { term: "Peek / пик", def: "Краткий выход из укрытия, чтобы увидеть или зафрагать врага." },
    { term: "Eco / эко", def: "Раунд экономии: покупаешь минимум, копишь на следующее оружие." },
    { term: "GG / WP", def: "Good Game / Well Played — уважение сопернику после матча." },
    { term: "Clutch", def: "Выигранный раунд в невыгодной ситуации (например 1v3)." },
    { term: "Hitreg", def: "Регистрация попаданий сервером; «плохой hitreg» = пули «не влетают»." },
    { term: "FOV", def: "Field of View — угол обзора камеры. Выше FOV = шире картинка." },
    { term: "Input lag", def: "Задержка между действием и реакцией на экране." },
    { term: "Nerf / Buff", def: "Ослабление / усиление персонажа, оружия или механики патчем." },
    { term: "QoL", def: "Quality of Life — удобства интерфейса без смены баланса." },
    { term: "Main", def: "Основной персонаж / роль / агент." },
    { term: "Throw", def: "Слитый раунд или карта из-за ошибки (или троллинга)." },
    { term: "Boost", def: "Накрутка ранга с более сильным игроком (часто против правил)." },
  ];

  // Реальные турниры подгружает content-hub.js (обновляются ежедневно)
  const TOURNAMENTS = [];

  const HIGHLIGHTS = [
    { nick: "s1mple*", team: "Легенда CS · хайлайты года", initials: "S1", c1: "#00f5ff", c2: "#8b5cff" },
    { nick: "Yatoro", team: "Team Spirit · carry", initials: "YT", c1: "#ff2bd6", c2: "#8b5cff" },
    { nick: "TenZ", team: "Sentinels · Valorant", initials: "TZ", c1: "#3dff9a", c2: "#00f5ff" },
    { nick: "Faker", team: "T1 · mid forever", initials: "FK", c1: "#ffc857", c2: "#ff2bd6" },
  ];

  const FALLBACK_DAILY = {
    date: "2026-09-24",
    updatedAt: "2026-09-24T20:00:00+03:00",
    gameOfTheDay: {
      title: "Counter-Strike 2",
      genre: "киберспорт",
      reason: "Свежий античит-патч + вечерний ранкид. Идеальный день для калибровки.",
      tip: "Играй с отключённым Xbox Game Bar и лимитом FPS = Hz монитора + 1.",
      platforms: ["PC"],
    },
    trending: [
      { title: "Valorant", note: "Новый агент на тесте — фаст-лобби забиты", heat: 96 },
      { title: "Elden Ring", note: "Кооп-рейды по DLC на пике", heat: 88 },
      { title: "Dota 2", note: "Патч 7.39e: мид снова имба", heat: 84 },
      { title: "Baldur's Gate 3", note: "Хардкорные таймлайн-ранны в тренде", heat: 79 },
      { title: "Apex Legends", note: "Сезонный реранк — окно для MMR", heat: 76 },
    ],
    tips: [
      "Сегодня вечером пинг к EU ниже обычного — хорошее окно для ranked.",
      "Не забывай обновлять GPU-драйверы перед крупными патчами.",
      "В Discord #поиск-тимы уже собирают 5-ки на CS2 после 21:00 MSK.",
    ],
  };

  const FALLBACK_DEALS = {
    updatedAt: "2026-09-24T23:11:13+03:00",
    source: "steam-specials-ru",
    deals: [
      {"id": "steam-678960", "title": "CODE VEIN", "store": "Steam", "old": 2099, "neu": 209, "pct": 90, "url": "https://store.steampowered.com/app/678960/?curator_clanid=0", "steamAppId": "678960"},
      {"id": "steam-1084160", "title": "Jagged Alliance 3", "store": "Steam", "old": 1999, "neu": 199, "pct": 90, "url": "https://store.steampowered.com/app/1084160/?curator_clanid=0", "steamAppId": "1084160"},
      {"id": "steam-246420", "title": "Kingdom Rush  - Tower Defense", "store": "Steam", "old": 460, "neu": 46, "pct": 90, "url": "https://store.steampowered.com/app/246420/", "steamAppId": "246420"},
      {"id": "steam-582660", "title": "Black Desert", "store": "Steam", "old": 350, "neu": 35, "pct": 90, "url": "https://store.steampowered.com/app/582660/?curator_clanid=0", "steamAppId": "582660"},
      {"id": "steam-617290", "title": "Remnant: From the Ashes", "store": "Steam", "old": 1297, "neu": 194, "pct": 85, "url": "https://store.steampowered.com/app/617290/?curator_clanid=0", "steamAppId": "617290"},
      {"id": "steam-640820", "title": "Pathfinder: Kingmaker — Enhanced Plus Edition", "store": "Steam", "old": 1079, "neu": 194, "pct": 82, "url": "https://store.steampowered.com/app/640820/?curator_clanid=0", "steamAppId": "640820"},
      {"id": "steam-1222140", "title": "Detroit: Become Human", "store": "Steam", "old": 2999, "neu": 599, "pct": 80, "url": "https://store.steampowered.com/app/1222140/?curator_clanid=0", "steamAppId": "1222140"},
      {"id": "steam-1282100", "title": "REMNANT II", "store": "Steam", "old": 2869, "neu": 573, "pct": 80, "url": "https://store.steampowered.com/app/1282100/?curator_clanid=0", "steamAppId": "1282100"},
    ],
  };

  const SPECS = {
    cp2077: {
      min: ["OS: Windows 10 64-bit", "CPU: Intel Core i5-3570K / AMD FX-8310", "RAM: 8 GB", "GPU: GTX 780 / Radeon RX 470", "SSD: 70 GB"],
      rec: ["OS: Windows 10 64-bit", "CPU: Intel Core i7-4790 / Ryzen 3 3200G", "RAM: 12 GB", "GPU: GTX 1060 6GB / RX 580", "SSD: 70 GB"],
    },
    elden: {
      min: ["OS: Windows 10", "CPU: Intel i5-8400 / Ryzen 3 3300X", "RAM: 12 GB", "GPU: GTX 1060 / RX 580", "HDD: 60 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i7-8700K / Ryzen 5 3600X", "RAM: 16 GB", "GPU: GTX 1070 / RX Vega 56", "SSD: 60 GB"],
    },
    bg3: {
      min: ["OS: Windows 10 64-bit", "CPU: Intel i5-4690 / AMD FX-8350", "RAM: 8 GB", "GPU: GTX 970 / RX 480", "SSD: 150 GB"],
      rec: ["OS: Windows 10 64-bit", "CPU: Intel i7-8700K / Ryzen 5 3600", "RAM: 16 GB", "GPU: RTX 2060 / RX 5700 XT", "SSD: 150 GB"],
    },
    cs2: {
      min: ["OS: Windows 10", "CPU: Intel Core 2 Duo E6600", "RAM: 8 GB", "GPU: GTX 720 / HD 7870", "SSD: 85 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i5 7xxx / Ryzen 5", "RAM: 16 GB", "GPU: GTX 1660 / RX 580", "SSD: 85 GB"],
    },
    valorant: {
      min: ["OS: Windows 10", "CPU: Intel i3-370M", "RAM: 4 GB", "GPU: Intel HD 3000", "HDD: 20+ GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i5 / Ryzen 5", "RAM: 8+ GB", "GPU: GTX 1050 Ti+", "SSD: рекомендуется"],
    },
    rdr2: {
      min: ["OS: Windows 10", "CPU: Intel i5-2500K / FX-8370", "RAM: 8 GB", "GPU: GTX 770 / Radeon R9 280", "HDD: 150 GB"],
      rec: ["OS: Windows 10", "CPU: Intel i7-4770K / Ryzen 5 1500X", "RAM: 12 GB", "GPU: GTX 1060 6GB / RX 480", "SSD: 150 GB"],
    },
    doom: {
      min: ["OS: Windows 10", "CPU: Intel i5 / Ryzen 3", "RAM: 8 GB", "GPU: GTX 1050 Ti / RX 470", "SSD: 50 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i7 / Ryzen 5", "RAM: 16 GB", "GPU: GTX 1660 / RTX 2060", "SSD: 80 GB"],
    },
    totalwar: {
      min: ["OS: Windows 10", "CPU: Intel i3 / Ryzen 3", "RAM: 6 GB", "GPU: GTX 900 / RX 400", "HDD: 120 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i5 / Ryzen 5", "RAM: 16 GB", "GPU: RTX 2060 / RX 5700", "SSD: 120 GB"],
    },
    forza5: {
      min: ["OS: Windows 10", "CPU: Intel i5-8400 / Ryzen 5 1600", "RAM: 8 GB", "GPU: GTX 1060 / RX 570", "SSD: 100 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i7 / Ryzen 7", "RAM: 16 GB", "GPU: RTX 3080 / RX 6800 XT", "SSD: 100 GB"],
    },
    re4: {
      min: ["OS: Windows 10", "CPU: Intel i5-7500 / Ryzen 3 1200", "RAM: 8 GB", "GPU: GTX 1050 Ti / RX 560", "SSD: 60 GB"],
      rec: ["OS: Windows 10/11", "CPU: Intel i7 / Ryzen 5", "RAM: 16 GB", "GPU: RTX 2070 / RX 6700 XT", "SSD: 60 GB"],
    },
  };

  const GPU_MULT = { budget: 0.55, mid: 1.0, high: 1.45, ultra: 1.9 };
  const CPU_MULT = { budget: 0.85, mid: 1.0, high: 1.1, ultra: 1.15 };
  const BASE_FPS = 95;
  const WISH_KEY = "nexus_pulse_wishlist";
  let lastNetworkLatency = null;
  const LANG_KEY = "nexus_pulse_lang";
  const MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const FIRST_CLASS = ["ru", "en", "uk", "de", "es", "fr", "pt", "pl", "tr", "zh", "ja", "ko"];

  const I18N = {
    ru: {
      "nav.games": "Игры", "nav.pulse": "Пульс", "nav.newGames": "Новинки", "nav.calendar": "Релизы", "nav.guides": "Гайды",
      "nav.esports": "Киберспорт", "nav.deals": "Скидки", "nav.tools": "Инструменты", "nav.news": "Новости",
      "nav.facts": "Факты", "nav.glossary": "Словарь", "nav.discord": "Discord",
      "hero.eyebrow": "Игровой хаб · 2026", "hero.title": "Каталог. Инструменты.", "hero.title2": "Ранкед без хаоса.",
      "hero.lead": "75 игр, ежедневный пульс, релизы и патчи, 30 гайдов, скидки, тест скорости и подбор игры под настроение — всё в одном месте.",
      "hero.ctaTools": "Открыть инструменты", "hero.ctaDiscord": "В Discord",
      "hero.statGames": "игр в каталоге", "hero.statGuides": "гайдов", "hero.statTools": "интерактивных тула",
      "pulse.eyebrow": "Ежедневно", "pulse.title": "Пульс дня", "pulse.desc": "Во что играть сегодня, тренды и горячие советы.",
      "pulse.gotd": "Игра дня", "pulse.trending": "Тренды сегодня", "pulse.tips": "Горячие советы",
      "newGames.eyebrow": "В фокусе", "newGames.title": "Новые интересные игры",
      "newGames.desc": "Свежие релизы, инди-находки, возвращения и ранний доступ — ежедневная подборка.",
      "newGames.updated": "Обновлено:",
      "cal.eyebrow": "Расписание", "cal.title": "Календарь релизов и патчей", "cal.desc": "Ближайшие релизы и свежие патчи.",
      "cal.releases": "Скоро выходит", "cal.patches": "Патчи · сегодня и недавно",
      "games.eyebrow": "Каталог", "games.title": "Топ игр", "games.desc": "Фильтруй по жанру, ищи по названию, сохраняй в избранное.",
      "games.search": "Поиск игры…", "games.empty": "Ничего не найдено. Сбрось фильтры или попробуй другой запрос.", "games.all": "Все",
      "guides.eyebrow": "Практика", "guides.title": "Гайды и советы", "guides.desc": "30 практических гайдов: FPS-настройки, ранкид, боссы, экономика, чеклисты.",
      "facts.eyebrow": "Любопытно", "facts.title": "Факты и лайфхаки", "facts.desc": "Короткие факты и приёмы, которые делают гейминг умнее.", "facts.next": "Ещё факт",
      "glossary.eyebrow": "Словарь", "glossary.title": "Словарь геймера", "glossary.desc": "Tilt, ping, smurf и другие слова из чата.",
      "esports.eyebrow": "Киберспорт", "esports.title": "Турниры и хайлайты", "esports.desc": "Ближайшие ивенты и игроки.",
      "esports.tournaments": "Ближайшие турниры", "esports.players": "Команды и игроки",
      "deals.eyebrow": "Скидки", "deals.title": "Горячие предложения", "deals.desc": "Скидки обновляются несколько раз в день.", "deals.updated": "Скидки обновлены:",
      "tools.eyebrow": "Инструменты", "tools.title": "Практические тулы", "tools.desc": "Подбор игры под настроение, FPS, системные требования, тест скорости и избранное.",
      "mood.title": "Подбор игры под настроение и время",
      "mood.desc": "Настроение + длительность + соло/мультиплеер → 3 рекомендации из каталога.",
      "mood.moodLabel": "Настроение", "mood.timeLabel": "Сколько времени", "mood.modeLabel": "Режим",
      "mood.chill": "Расслабиться", "mood.compete": "Посоревноваться", "mood.story": "Сюжет / погружение",
      "mood.horror": "Пощекотать нервы", "mood.coop": "С друзьями", "mood.grind": "Погриндзить",
      "mood.short": "15–30 мин", "mood.hour": "~1 час", "mood.long": "2+ часа", "mood.binge": "Весь вечер",
      "mood.any": "Не важно", "mood.solo": "Соло", "mood.multi": "Мультиплеер",
      "mood.run": "Подобрать игры", "mood.again": "Подобрать ещё",
      "mood.why": "Почему:", "mood.empty": "Не нашлось точных совпадений — вот ближайшие варианты.",
      "tools.fps": "Оценка FPS", "tools.fpsDesc": "Выбери игру и уровень железа — получи ориентировочный FPS.",
      "tools.game": "Игра", "tools.gpu": "Уровень GPU", "tools.cpu": "Уровень CPU", "tools.calc": "Рассчитать",
      "tools.specs": "Системные требования", "tools.specsDesc": "Сравни минимальные и рекомендованные спеки игры.",
      "tools.showSpecs": "Показать требования", "tools.min": "Минимальные", "tools.rec": "Рекомендованные",
      "tools.wish": "Избранное", "tools.wishDesc": "Сохраняй игры сердечком в каталоге.",
      "tools.wishEmpty": "Пока пусто. Добавь игры из каталога ↑", "tools.clearWish": "Очистить избранное",
      "speed.title": "Тест скорости", "speed.desc": "Скорость загрузки и пинг — подходит ли сеть для онлайна.",
      "speed.run": "Проверить скорость", "speed.again": "Проверить снова", "speed.progress": "Идёт замер…",
      "speed.download": "Загрузка", "speed.latency": "Пинг", "speed.rating": "Для онлайна",
      "speed.err": "Не удалось измерить скорость. Проверь подключение или отключи блокировщик.",
      "speed.excellent": "Отлично", "speed.ok": "Нормально", "speed.weak": "Слабо для онлайн",
      "news.eyebrow": "Лента", "news.title": "Новости гейминга", "news.desc": "Свежие заголовки дня.",
      "community.eyebrow": "Комьюнити", "community.title": "Залетай в Discord NEXUS PULSE",
      "community.lead": "Халява, скидки, большие матчи и поиск тимы — в одном месте. Лента на сервере обновляется сама каждый день.", "community.join": "Присоединиться",
      "lang.label": "Язык", "lang.popular": "Популярные", "lang.all": "Все языки", "lang.search": "Поиск языка…",
      "pwa.install": "Установить",
    },
    en: {
      "nav.games": "Games", "nav.pulse": "Pulse", "nav.newGames": "New picks", "nav.calendar": "Releases", "nav.guides": "Guides",
      "nav.esports": "Esports", "nav.deals": "Deals", "nav.tools": "Tools", "nav.news": "News",
      "nav.facts": "Facts", "nav.glossary": "Glossary", "nav.discord": "Discord",
      "hero.eyebrow": "Gaming hub · 2026", "hero.title": "Catalog. Tools.", "hero.title2": "Ranked without chaos.",
      "hero.lead": "75 games, daily pulse, releases & patches, 30 guides, deals, speed test and mood-based picks — all in one place.",
      "hero.ctaTools": "Open tools", "hero.ctaDiscord": "Join Discord",
      "hero.statGames": "games in catalog", "hero.statGuides": "guides", "hero.statTools": "interactive tools",
      "pulse.eyebrow": "Daily", "pulse.title": "Pulse of the day", "pulse.desc": "What to play today, trends and hot tips.",
      "pulse.gotd": "Game of the day", "pulse.trending": "Trending today", "pulse.tips": "Hot tips",
      "newGames.eyebrow": "Spotlight", "newGames.title": "New interesting games",
      "newGames.desc": "Fresh releases, indie finds, comebacks and early access — daily picks.",
      "newGames.updated": "Updated:",
      "cal.eyebrow": "Schedule", "cal.title": "Release & patch calendar", "cal.desc": "Upcoming releases and recent patches.",
      "cal.releases": "Coming soon", "cal.patches": "Patches · today & recent",
      "games.eyebrow": "Catalog", "games.title": "Top games", "games.desc": "Filter by genre, search, save favorites.",
      "games.search": "Search games…", "games.empty": "Nothing found. Reset filters or try another query.", "games.all": "All",
      "guides.eyebrow": "Practice", "guides.title": "Guides & tips", "guides.desc": "30 practical guides: FPS settings, ranked climb, bosses, economy, beginner checklists.",
      "facts.eyebrow": "Curious", "facts.title": "Facts & lifehacks", "facts.desc": "Short facts and tricks that make gaming smarter.", "facts.next": "Next fact",
      "glossary.eyebrow": "Glossary", "glossary.title": "Gamer glossary", "glossary.desc": "Tilt, ping, smurf and other chat essentials.",
      "esports.eyebrow": "Esports", "esports.title": "Tournaments & highlights", "esports.desc": "Upcoming events and players to watch.",
      "esports.tournaments": "Upcoming tournaments", "esports.players": "Teams & players",
      "deals.eyebrow": "Deals", "deals.title": "Hot offers", "deals.desc": "Deals refresh several times a day.", "deals.updated": "Deals updated:",
      "tools.eyebrow": "Tools", "tools.title": "Practical tools", "tools.desc": "Mood-based game picker, FPS, system specs, speed test and wishlist.",
      "mood.title": "Pick a game by mood & time",
      "mood.desc": "Mood + session length + solo/multiplayer → 3 catalog recommendations.",
      "mood.moodLabel": "Mood", "mood.timeLabel": "Session length", "mood.modeLabel": "Mode",
      "mood.chill": "Chill", "mood.compete": "Compete", "mood.story": "Story / immersion",
      "mood.horror": "Get spooked", "mood.coop": "With friends", "mood.grind": "Grind",
      "mood.short": "15–30 min", "mood.hour": "~1 hour", "mood.long": "2+ hours", "mood.binge": "Whole evening",
      "mood.any": "Either", "mood.solo": "Solo", "mood.multi": "Multiplayer",
      "mood.run": "Find games", "mood.again": "Pick again",
      "mood.why": "Why:", "mood.empty": "No exact matches — here are the closest picks.",
      "tools.fps": "FPS estimate", "tools.fpsDesc": "Pick a game and hardware tier for a rough FPS estimate.",
      "tools.game": "Game", "tools.gpu": "GPU tier", "tools.cpu": "CPU tier", "tools.calc": "Calculate",
      "tools.specs": "System requirements", "tools.specsDesc": "Compare minimum and recommended specs.",
      "tools.showSpecs": "Show requirements", "tools.min": "Minimum", "tools.rec": "Recommended",
      "tools.wish": "Wishlist", "tools.wishDesc": "Heart games in the catalog to save them.",
      "tools.wishEmpty": "Empty for now. Add games from the catalog ↑", "tools.clearWish": "Clear wishlist",
      "speed.title": "Speed test", "speed.desc": "Download speed and ping — is your connection good for online play.",
      "speed.run": "Test speed", "speed.again": "Test again", "speed.progress": "Measuring…",
      "speed.download": "Download", "speed.latency": "Ping", "speed.rating": "For online play",
      "speed.err": "Could not measure speed. Check your connection or disable ad blockers.",
      "speed.excellent": "Excellent", "speed.ok": "Okay", "speed.weak": "Weak for online",
      "news.eyebrow": "Feed", "news.title": "Gaming news", "news.desc": "Today's fresh headlines.",
      "community.eyebrow": "Community", "community.title": "Join NEXUS PULSE Discord",
      "community.lead": "Freebies, deals, big matches and team finder in one place. The server feed updates itself every day.", "community.join": "Join",
      "lang.label": "Language", "lang.popular": "Popular", "lang.all": "All languages", "lang.search": "Search language…",
      "pwa.install": "Install",
    },
  };

  ["uk", "de", "es", "fr", "pt", "pl", "tr", "zh", "ja", "ko"].forEach((code) => {
    I18N[code] = Object.assign({}, I18N.en);
  });
  Object.assign(I18N.uk, { "nav.games": "Ігри", "nav.pulse": "Пульс", "nav.guides": "Гайди", "nav.deals": "Знижки", "nav.tools": "Інструменти", "nav.facts": "Факти", "nav.glossary": "Словник", "hero.ctaTools": "Відкрити інструменти", "pulse.title": "Пульс дня", "games.title": "Топ ігор", "speed.title": "Тест швидкості", "speed.run": "Перевірити швидкість", "speed.again": "Перевірити знову", "deals.updated": "Знижки оновлено:", "lang.label": "Мова", "nav.newGames": "Новинки", "newGames.title": "Нові цікаві ігри", "newGames.updated": "Оновлено:", "pwa.install": "Встановити" });
  Object.assign(I18N.de, { "nav.games": "Spiele", "nav.pulse": "Puls", "nav.guides": "Guides", "nav.deals": "Angebote", "nav.tools": "Tools", "nav.facts": "Fakten", "nav.glossary": "Glossar", "hero.ctaTools": "Tools öffnen", "pulse.title": "Puls des Tages", "games.title": "Top-Spiele", "speed.title": "Speedtest", "speed.run": "Geschwindigkeit prüfen", "speed.again": "Erneut prüfen", "deals.updated": "Angebote aktualisiert:", "lang.label": "Sprache", "nav.newGames": "Neuheiten", "newGames.title": "Neue spannende Spiele", "newGames.updated": "Aktualisiert:" });
  Object.assign(I18N.es, { "nav.games": "Juegos", "nav.pulse": "Pulso", "nav.guides": "Guías", "nav.deals": "Ofertas", "nav.tools": "Herramientas", "nav.facts": "Datos", "nav.glossary": "Glosario", "hero.ctaTools": "Abrir herramientas", "pulse.title": "Pulso del día", "games.title": "Top juegos", "speed.title": "Test de velocidad", "speed.run": "Probar velocidad", "speed.again": "Probar de nuevo", "deals.updated": "Ofertas actualizadas:", "lang.label": "Idioma", "nav.newGames": "Novedades", "newGames.title": "Juegos nuevos e interesantes", "newGames.updated": "Actualizado:" });
  Object.assign(I18N.fr, { "nav.games": "Jeux", "nav.pulse": "Pulse", "nav.guides": "Guides", "nav.deals": "Promos", "nav.tools": "Outils", "nav.facts": "Faits", "nav.glossary": "Glossaire", "hero.ctaTools": "Ouvrir les outils", "pulse.title": "Pulse du jour", "games.title": "Top jeux", "speed.title": "Test de débit", "speed.run": "Tester la vitesse", "speed.again": "Retester", "deals.updated": "Promos mises à jour :", "lang.label": "Langue", "nav.newGames": "Nouveautés", "newGames.title": "Nouveaux jeux intéressants", "newGames.updated": "Mis à jour :" });
  Object.assign(I18N.pt, { "nav.games": "Jogos", "nav.pulse": "Pulso", "nav.guides": "Guias", "nav.deals": "Ofertas", "nav.tools": "Ferramentas", "nav.facts": "Fatos", "nav.glossary": "Glossário", "hero.ctaTools": "Abrir ferramentas", "pulse.title": "Pulso do dia", "games.title": "Top jogos", "speed.title": "Teste de velocidade", "speed.run": "Testar velocidade", "speed.again": "Testar de novo", "deals.updated": "Ofertas atualizadas:", "lang.label": "Idioma", "nav.newGames": "Novidades", "newGames.title": "Jogos novos e interessantes", "newGames.updated": "Atualizado:" });
  Object.assign(I18N.pl, { "nav.games": "Gry", "nav.pulse": "Puls", "nav.guides": "Poradniki", "nav.deals": "Promocje", "nav.tools": "Narzędzia", "nav.facts": "Fakty", "nav.glossary": "Słownik", "hero.ctaTools": "Otwórz narzędzia", "pulse.title": "Puls dnia", "games.title": "Top gry", "speed.title": "Test prędkości", "speed.run": "Sprawdź prędkość", "speed.again": "Sprawdź ponownie", "deals.updated": "Promocje zaktualizowane:", "lang.label": "Język", "nav.newGames": "Nowości", "newGames.title": "Nowe ciekawe gry", "newGames.updated": "Zaktualizowano:" });
  Object.assign(I18N.tr, { "nav.games": "Oyunlar", "nav.pulse": "Nabız", "nav.guides": "Rehberler", "nav.deals": "Fırsatlar", "nav.tools": "Araçlar", "nav.facts": "Bilgiler", "nav.glossary": "Sözlük", "hero.ctaTools": "Araçları aç", "pulse.title": "Günün nabzı", "games.title": "En iyi oyunlar", "speed.title": "Hız testi", "speed.run": "Hızı ölç", "speed.again": "Tekrar ölç", "deals.updated": "Fırsatlar güncellendi:", "lang.label": "Dil", "nav.newGames": "Yeniler", "newGames.title": "Yeni ilginç oyunlar", "newGames.updated": "Güncellendi:" });
  Object.assign(I18N.zh, { "nav.games": "游戏", "nav.pulse": "今日脉搏", "nav.guides": "攻略", "nav.deals": "优惠", "nav.tools": "工具", "nav.facts": "冷知识", "nav.glossary": "术语", "hero.ctaTools": "打开工具", "pulse.title": "今日脉搏", "games.title": "热门游戏", "speed.title": "网速测试", "speed.run": "开始测试", "speed.again": "重新测试", "deals.updated": "优惠更新于：", "lang.label": "语言", "nav.newGames": "新作", "newGames.title": "新趣游戏", "newGames.updated": "更新于：" });
  Object.assign(I18N.ja, { "nav.games": "ゲーム", "nav.pulse": "本日のパルス", "nav.guides": "ガイド", "nav.deals": "セール", "nav.tools": "ツール", "nav.facts": "豆知識", "nav.glossary": "用語集", "hero.ctaTools": "ツールを開く", "pulse.title": "本日のパルス", "games.title": "人気ゲーム", "speed.title": "速度テスト", "speed.run": "速度を測定", "speed.again": "再測定", "deals.updated": "セール更新：", "lang.label": "言語", "nav.newGames": "新作", "newGames.title": "注目の新作ゲーム", "newGames.updated": "更新：" });
  Object.assign(I18N.ko, { "nav.games": "게임", "nav.pulse": "오늘의 펄스", "nav.guides": "가이드", "nav.deals": "할인", "nav.tools": "도구", "nav.facts": "팩트", "nav.glossary": "용어집", "hero.ctaTools": "도구 열기", "pulse.title": "오늘의 펄스", "games.title": "인기 게임", "speed.title": "속도 테스트", "speed.run": "속도 측정", "speed.again": "다시 측정", "deals.updated": "할인 업데이트:", "lang.label": "언어", "nav.newGames": "신작", "newGames.title": "새로운 흥미로운 게임", "newGames.updated": "업데이트:" });

  /* Ключи новых разделов: новости, видео, трансляции */
  Object.assign(I18N.ru, {
    "nav.videos": "Видео", "videos.eyebrow": "Смотреть", "videos.title": "Видео и стримы",
    "videos.desc": "Свежие ролики про игры, киберспорт и ИИ — смотри прямо здесь.",
    "news.desc": "Главные игровые новости дня — с картинками и полным текстом.",
    "esports.title": "Турниры, матчи и трансляции", "esports.desc": "Расписание матчей по московскому времени и официальные трансляции прямо на сайте.",
    "esports.tournaments": "Турниры", "esports.watch": "Смотреть трансляцию", "esports.matches": "Матчи",
    "cal.desc": "Ближайшие релизы на ПК, PlayStation, Xbox и Switch и свежие обновления популярных игр.",
    "newGames.desc": "Самые популярные игры, вышедшие за последние недели.",
    "guides.desc": "30 подробных гайдов: FPS и Windows, настройки игр, советы новичкам и разбор частых ошибок.",
  });
  const NP_EN_NEW = {
    "nav.videos": "Videos", "videos.eyebrow": "Watch", "videos.title": "Videos & streams",
    "videos.desc": "Fresh videos about games, esports and AI — watch right here.",
    "news.desc": "Top gaming news of the day — with pictures and full text.",
    "esports.title": "Tournaments, matches & streams", "esports.desc": "Match schedule in Moscow time and official broadcasts right on the site.",
    "esports.tournaments": "Tournaments", "esports.watch": "Watch the broadcast", "esports.matches": "Matches",
    "cal.desc": "Upcoming releases on PC, PlayStation, Xbox and Switch plus fresh updates for popular games.",
    "newGames.desc": "The most popular games released in recent weeks.",
    "guides.desc": "30 detailed guides: FPS & Windows, game settings, beginner tips and common mistakes.",
  };
  ["en", "de", "es", "fr", "pt", "pl", "tr", "zh", "ja", "ko"].forEach((code) => Object.assign(I18N[code], NP_EN_NEW));
  Object.assign(I18N.uk, NP_EN_NEW, {
    "nav.videos": "Відео", "videos.eyebrow": "Дивитися", "videos.title": "Відео та стріми",
    "videos.desc": "Свіжі ролики про ігри, кіберспорт і ШІ — дивись просто тут.",
    "news.desc": "Головні ігрові новини дня — з картинками та повним текстом.",
    "esports.title": "Турніри, матчі та трансляції", "esports.desc": "Розклад матчів за московським часом і офіційні трансляції просто на сайті.",
    "esports.tournaments": "Турніри", "esports.watch": "Дивитися трансляцію", "esports.matches": "Матчі",
    "cal.desc": "Найближчі релізи на ПК, PlayStation, Xbox і Switch та свіжі оновлення популярних ігор.",
    "newGames.desc": "Найпопулярніші ігри, що вийшли за останні тижні.",
    "guides.desc": "30 докладних гайдів: FPS і Windows, налаштування ігор, поради новачкам і типові помилки.",
  });

  const WORLD_LANGS = [
    ["af","Afrikaans"],["sq","Shqip"],["am","አማርኛ"],["ar","العربية"],["hy","Հայերեն"],["az","Azərbaycan"],
    ["eu","Euskara"],["be","Беларуская"],["bn","বাংলা"],["bs","Bosanski"],["bg","Български"],["ca","Català"],
    ["ceb","Cebuano"],["zh-CN","简体中文"],["zh-TW","繁體中文"],["co","Corsu"],["hr","Hrvatski"],["cs","Čeština"],
    ["da","Dansk"],["nl","Nederlands"],["en","English"],["eo","Esperanto"],["et","Eesti"],["fi","Suomi"],
    ["fr","Français"],["fy","Frysk"],["gl","Galego"],["ka","ქართული"],["de","Deutsch"],["el","Ελληνικά"],
    ["gu","ગુજરાતી"],["ht","Kreyòl ayisyen"],["ha","Hausa"],["haw","ʻŌlelo Hawaiʻi"],["he","עברית"],["hi","हिन्दी"],
    ["hmn","Hmong"],["hu","Magyar"],["is","Íslenska"],["ig","Igbo"],["id","Bahasa Indonesia"],["ga","Gaeilge"],
    ["it","Italiano"],["ja","日本語"],["jv","Basa Jawa"],["kn","ಕನ್ನಡ"],["kk","Қазақ"],["km","ខ្មែរ"],
    ["rw","Kinyarwanda"],["ko","한국어"],["ku","Kurdî"],["ky","Кыргызча"],["lo","ລາວ"],["la","Latina"],
    ["lv","Latviešu"],["lt","Lietuvių"],["lb","Lëtzebuergesch"],["mk","Македонски"],["mg","Malagasy"],["ms","Bahasa Melayu"],
    ["ml","മലയാളം"],["mt","Malti"],["mi","Māori"],["mr","मराठी"],["mn","Монгол"],["my","မြန်မာ"],
    ["ne","नेपाली"],["no","Norsk"],["ny","Chichewa"],["or","ଓଡ଼ିଆ"],["ps","پښتو"],["fa","فارسی"],
    ["pl","Polski"],["pt","Português"],["pa","ਪੰਜਾਬੀ"],["ro","Română"],["ru","Русский"],["sm","Samoa"],
    ["gd","Gàidhlig"],["sr","Српски"],["st","Sesotho"],["sn","Shona"],["sd","سنڌي"],["si","සිංහල"],
    ["sk","Slovenčina"],["sl","Slovenščina"],["so","Soomaali"],["es","Español"],["su","Basa Sunda"],["sw","Kiswahili"],
    ["sv","Svenska"],["tl","Tagalog"],["tg","Тоҷикӣ"],["ta","தமிழ்"],["tt","Татар"],["te","తెలుగు"],
    ["th","ไทย"],["tr","Türkçe"],["tk","Türkmen"],["uk","Українська"],["ur","اردو"],["ug","ئۇيغۇرچە"],
    ["uz","Oʻzbek"],["vi","Tiếng Việt"],["cy","Cymraeg"],["xh","isiXhosa"],["yi","ייִדיש"],["yo","Yorùbá"],["zu","isiZulu"],
  ];
  const POPULAR_LANGS = ["ru","en","uk","de","es","fr","pt","pl","tr","zh-CN","ja","ko","ar","hi","it","nl"];

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  function getWishlist() {
    try { return JSON.parse(localStorage.getItem(WISH_KEY) || "[]"); }
    catch { return []; }
  }
  function setWishlist(ids) { localStorage.setItem(WISH_KEY, JSON.stringify(ids)); }

  function formatRub(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return v.toLocaleString("ru-RU") + " ₽";
  }
  function dealNewPrice(d) {
    const v = d && (d.neu ?? d.new ?? d.price);
    return Number(v);
  }
  function storeSearchUrl(title, store, steamAppId) {
    if (steamAppId) return `https://store.steampowered.com/app/${steamAppId}/`;
    const q = encodeURIComponent(title || "");
    const s = String(store || "").toLowerCase();
    if (s.includes("steam")) return `https://store.steampowered.com/search/?term=${q}`;
    if (s.includes("epic")) return `https://store.epicgames.com/en-US/browse?q=${q}`;
    if (s.includes("play")) return `https://store.playstation.com/search/${q}`;
    if (s.includes("xbox")) return `https://www.xbox.com/en-US/search?q=${q}`;
    if (s.includes("nintendo")) return `https://www.nintendo.com/search/#q=${q}&p=1&tab=software`;
    return `https://www.google.com/search?q=${q}+${encodeURIComponent(store || "game")}+sale`;
  }
  function openContentModal({ kicker, title, bodyHtml, actionsHtml }) {
    const modal = $("#contentModal");
    if (!modal) return;
    const k = $("#modalKicker");
    const tEl = $("#modalTitle");
    const body = $("#modalBody");
    const actions = $("#modalActions");
    if (k) k.textContent = kicker || "";
    if (tEl) tEl.textContent = title || "";
    if (body) body.innerHTML = bodyHtml || "";
    if (actions) actions.innerHTML = actionsHtml || "";
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    $("#contentModal .np-modal-close")?.focus();
  }
  function closeContentModal() {
    const modal = $("#contentModal");
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = "";
  }
  function formatIsoDateRu(iso) {
    if (!iso) return "—";
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    return `${Number(m[3])} ${MONTHS_RU[Number(m[2]) - 1] || m[2]} ${m[1]}`;
  }
  function formatUpdatedAt(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return formatIsoDateRu(iso);
      return d.toLocaleString("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    } catch { return formatIsoDateRu(iso); }
  }
  function platformsHtml(list) {
    return (list || []).map((p) => `<span class="plat">${p}</span>`).join("");
  }
  function isDiscordReady() {
    const u = (DISCORD_INVITE_URL || "").trim();
    return u.length > 0 && u !== "#";
  }
  function currentLangCode() { return (localStorage.getItem(LANG_KEY) || "ru").trim(); }
  function currentLangBase() {
    const raw = currentLangCode();
    if (raw === "zh-CN" || raw === "zh-TW" || raw === "zh") return "zh";
    const base = raw.split("-")[0];
    return FIRST_CLASS.includes(base) ? base : "en";
  }
  function t(key) {
    const lang = currentLangBase();
    return (I18N[lang] && I18N[lang][key]) || I18N.ru[key] || key;
  }

  function wireDiscord() {
    const ready = isDiscordReady();
    const url = ready ? DISCORD_INVITE_URL.trim() : "#";
    $$(".discord-cta").forEach((el) => {
      if (ready) {
        el.href = url; el.target = "_blank"; el.rel = "noopener noreferrer";
        el.classList.remove("is-disabled", "btn-soon");
        if (el.id === "discordCta") el.textContent = t("community.join");
      } else {
        el.href = "#community"; el.removeAttribute("target"); el.classList.add("is-disabled");
        if (el.id === "discordCta") {
          el.classList.add("btn-soon"); el.classList.remove("is-disabled");
          el.textContent = "Скоро"; el.href = "#";
          el.addEventListener("click", (e) => e.preventDefault());
        }
      }
    });
    const hero = $("#heroDiscordBtn");
    if (hero) {
      if (ready) {
        hero.href = url; hero.target = "_blank"; hero.rel = "noopener noreferrer";
        hero.textContent = t("hero.ctaDiscord");
      } else {
        hero.href = "#community"; hero.removeAttribute("target"); hero.textContent = "Комьюнити";
      }
    }
    const soon = $("#discordSoon");
    if (soon) soon.hidden = ready;
  }

  // Навигация в шапке (выпадающие меню, мобильное меню, поиск) — nav.js
  const toTop = $("#toTop");
  window.addEventListener("scroll", () => toTop?.classList.toggle("visible", window.scrollY > 500));
  toTop?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

  let activeGenre = "all";
  let searchQuery = "";

  function renderGames() {
    const grid = $("#gamesGrid");
    const empty = $("#gamesEmpty");
    if (!grid) return;
    const wish = new Set(getWishlist());
    const q = searchQuery.trim().toLowerCase();
    const filtered = GAMES.filter((g) => {
      const byGenre = activeGenre === "all" || g.genre === activeGenre;
      const bySearch = !q || g.title.toLowerCase().includes(q) || g.genre.toLowerCase().includes(q) || g.platforms.some((p) => p.toLowerCase().includes(q));
      return byGenre && bySearch;
    });
    if (empty) empty.hidden = filtered.length > 0;
    grid.innerHTML = filtered.map((g) => `
      <article class="game-card" data-id="${g.id}">
        <div class="card-cover" style="--c1:${g.color[0]};--c2:${g.color[1]}">
          <span class="badge">${g.genre}</span>
          <button class="fav-btn ${wish.has(g.id) ? "active" : ""}" type="button" data-fav="${g.id}" aria-label="Wishlist">♥</button>
          <span>${g.title.split(" ")[0].toUpperCase()}</span>
        </div>
        <div class="card-body">
          <h3>${g.title}</h3>
          <div class="card-meta">
            <span class="rating">★ ${g.rating.toFixed(1)}</span>
            <div class="platforms">${platformsHtml(g.platforms)}</div>
          </div>
          <p class="card-desc">${g.desc}</p>
        </div>
      </article>`).join("");
  }

  $("#genreFilters")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    $$("#genreFilters .chip").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    activeGenre = btn.dataset.genre;
    rerenderGames();
  });
  $("#gameSearch")?.addEventListener("input", (e) => { searchQuery = e.target.value; rerenderGames(); });
  // features-extra.js оборачивает renderGames (доп. фильтры, бейджи) — вызываем обёртку, если она есть
  function rerenderGames() {
    const np = window.NexusPulse;
    if (np && typeof np.renderGames === "function") np.renderGames(); else renderGames();
  }
  $("#gamesGrid")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-fav]");
    if (!btn) return;
    const id = btn.dataset.fav;
    let wish = getWishlist();
    wish = wish.includes(id) ? wish.filter((x) => x !== id) : wish.concat(id);
    setWishlist(wish);
    rerenderGames();
    renderWishlist();
  });

  function renderGuides() {
    const el = $("#guidesGrid");
    if (!el) return;
    el.innerHTML = GUIDES.map((g, i) => `
      <button type="button" class="guide-card glass" data-guide-index="${i}" aria-label="Открыть гайд: ${g.title}">
        <span class="guide-tag">${g.tag}</span>
        <h3>${g.title}</h3>
        <p class="guide-preview">${g.text}</p>
        <div class="guide-meta">⏱ ${g.time}</div>
        <span class="guide-open">Открыть гайд →</span>
      </button>`).join("");
  }

  function openGuide(index) {
    const g = GUIDES[index];
    if (!g) return;
    const steps = String(g.text || "").split(/(?<=\.)\s+/).filter(Boolean);
    const bodyHtml = `
      <p>${g.text}</p>
      <p><strong>Краткий чеклист</strong></p>
      <ul>${steps.map((s) => `<li>${s}</li>`).join("")}</ul>
      <p>Время на прочтение: ${g.time}. Тема: ${g.tag}.</p>`;
    openContentModal({
      kicker: "Гайд · " + g.tag,
      title: g.title,
      bodyHtml,
      actionsHtml: `<button type="button" class="primary" data-close-modal>Понятно</button>`,
    });
  }

  let factIndex = Math.floor(Math.random() * FACTS.length);
  function renderFact() {
    const el = $("#factText");
    if (el) el.textContent = FACTS[factIndex % FACTS.length];
  }
  $("#factNext")?.addEventListener("click", () => { factIndex = (factIndex + 1) % FACTS.length; renderFact(); });

  function renderGlossary() {
    const el = $("#glossaryGrid");
    if (!el) return;
    el.innerHTML = GLOSSARY.map((g) => `
      <article class="glossary-card glass">
        <h3>${g.term}</h3>
        <p>${g.def}</p>
      </article>`).join("");
  }

  function renderEsports() {
    const tl = $("#tournamentsList");
    if (tl) tl.innerHTML = TOURNAMENTS.map((t) => `
      <li>
        <span class="t-date">${t.date}</span>
        <div><div class="t-name">${t.name}</div><div class="t-game">${t.game}</div></div>
        <span class="t-prize">${t.prize}</span>
      </li>`).join("");
    const hg = $("#highlightsGrid");
    if (hg) hg.innerHTML = HIGHLIGHTS.map((h) => `
      <article class="highlight-card glass">
        <div class="hl-avatar" style="--c1:${h.c1};--c2:${h.c2}">${h.initials}</div>
        <div class="hl-info"><strong>${h.nick}</strong><span>${h.team}</span></div>
      </article>`).join("");
  }


  function renderNewGames(daily) {
    const grid = $("#newGamesGrid");
    const list = (daily && daily.newInterestingGames) || [];
    if (grid) {
      grid.innerHTML = list.map((g) => `
        <article class="new-game-card">
          <div class="card-cover" style="--c1:${g.c1 || "#1a1030"};--c2:${g.c2 || "#3a1858"}">
            ${g.tag ? `<span class="new-game-tag" data-tag="${g.tag}">${g.tag}</span>` : ""}
          </div>
          <div class="card-body">
            <h3>${g.title}</h3>
            <p class="new-game-genre">${g.genre || ""}</p>
            <p class="new-game-blurb">${g.blurb || ""}</p>
            <div class="new-game-meta">
              <div class="platforms">${platformsHtml(g.platforms)}</div>
              <span class="new-game-date">${formatIsoDateRu(g.date)}</span>
            </div>
          </div>
        </article>`).join("");
    }
    const updated = $("#newGamesUpdated");
    if (updated) {
      const d = (daily && daily.date) || "";
      if (d) updated.dataset.date = d;
      updated.textContent = `${t("newGames.updated")} ${formatIsoDateRu(d)}`;
    }
  }

  function renderPulse(daily) {
    const gotd = daily.gameOfTheDay || {};
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set("#gotdTitle", gotd.title || "—");
    set("#gotdGenre", gotd.genre || "");
    set("#gotdReason", gotd.reason || "");
    set("#gotdTip", gotd.tip || "");
    const plats = $("#gotdPlatforms");
    if (plats) plats.innerHTML = platformsHtml(gotd.platforms);
    const trending = $("#trendingList");
    if (trending) trending.innerHTML = (daily.trending || []).map((t) => `
      <li><div><span class="trend-title">${t.title}</span><span class="trend-note">${t.note || ""}</span></div>
      <span class="trend-heat">${t.heat ?? "—"}°</span></li>`).join("");
    const tips = $("#tipsList");
    if (tips) tips.innerHTML = (daily.tips || []).map((x, i) => `
      <li class="tip-item" data-tip-index="${i}" tabindex="0" role="button" aria-label="Открыть совет">
        <span class="tip-text">${x}</span>
        <span class="tip-open">Открыть →</span>
      </li>`).join("");
    tips.dataset.tips = JSON.stringify(daily.tips || []);
    const updated = $("#pulseUpdated");
    if (updated) updated.textContent = `Обновлено: ${formatIsoDateRu(daily.date)}`;
  }

  function renderCalendar(daily) {
    const releases = $("#releasesList");
    if (releases) releases.innerHTML = (daily.releases || []).map((r) => `
      <li><div class="cal-date">${formatIsoDateRu(r.date)}</div>
      <div class="cal-body"><strong>${r.title}</strong>
      <div class="platforms">${platformsHtml(r.platforms)}</div>
      <p class="cal-note">${r.note || ""}</p></div></li>`).join("");
    const patches = $("#patchesList");
    if (patches) patches.innerHTML = (daily.patches || []).map((p) => `
      <li><div class="cal-date">${formatIsoDateRu(p.date)}${p.label ? `<span class="cal-label">${p.label}</span>` : ""}</div>
      <div class="cal-body"><strong>${p.game}</strong>
      <div class="platforms">${platformsHtml(p.platforms)}</div>
      <p class="cal-note">${p.note || ""}</p></div></li>`).join("");
  }

  function renderDeals(payload) {
    const list = (payload && payload.deals) || [];
    const updated = $("#dealsUpdated");
    if (updated) {
      updated.textContent = `${t("deals.updated")} ${formatUpdatedAt(payload && payload.updatedAt)}`;
      if (payload && payload.updatedAt) updated.dataset.ts = payload.updatedAt;
    }
    const ticker = $("#dealsTicker");
    if (ticker) {
      const items = list.map((d) => {
        const neu = dealNewPrice(d);
        const pct = Number(d.pct);
        const pctLabel = Number.isFinite(pct) ? `−${pct}%` : "SALE";
        return `<span class="ticker-item">${d.title}${d.store ? ` · ${d.store}` : ""}: <b>${pctLabel}</b> · ${formatRub(neu)}</span>`;
      });
      ticker.innerHTML = [...items, ...items].join("");
    }
    const grid = $("#dealsGrid");
    if (grid) {
      grid.innerHTML = list.map((d, i) => {
        const neu = dealNewPrice(d);
        const old = Number(d.old);
        const pct = Number(d.pct);
        const pctLabel = Number.isFinite(pct) ? `−${pct}%` : "SALE";
        const save = (Number.isFinite(old) && Number.isFinite(neu) && old > neu)
          ? `Экономия ${formatRub(old - neu)}`
          : "";
        const href = d.url || storeSearchUrl(d.title, d.store, d.steamAppId);
        return `
      <article class="deal-card" data-deal-index="${i}" data-deal-url="${href}" role="link" tabindex="0" aria-label="Открыть скидку: ${d.title}">
        <div class="card-cover" style="--c1:#102018;--c2:#183828">
          <span class="deal-store-badge">${d.store || "SALE"}</span>
          <span class="deal-pct">${pctLabel}</span>
        </div>
        <div class="card-body">
          <h3>${d.title}</h3>
          <div class="deal-prices">
            <span class="price-old">${formatRub(old)}</span>
            <span class="price-new">${formatRub(neu)}</span>
            <span class="discount-badge">${pctLabel}</span>
          </div>
          ${save ? `<div class="deal-save">${save}</div>` : ""}
          <div class="deal-open">Открыть в ${d.store || "магазине"} →</div>
        </div>
      </article>`;
      }).join("");
      grid.dataset.deals = JSON.stringify(list);
    }
  }

  function renderNews(news) {
    const grid = $("#newsGrid");
    if (!grid) return;
    grid.innerHTML = (news || []).map((n) => `
      <article class="news-card glass">
        <div class="card-cover" style="--c1:${n.c1 || "#101828"};--c2:${n.c2 || "#182848"}"></div>
        <div class="card-body">
          <div class="news-date">${n.date}</div>
          <h3>${n.title}</h3>
          <p>${n.text}</p>
        </div>
      </article>`).join("");
  }

  function applyDaily(daily) {
    // Календарь, новинки и новости рендерит content-hub.js из ежедневно обновляемых файлов
    renderPulse(daily);
  }

  async function loadDaily() {
    try {
      const res = await fetch("./data/daily.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      applyDaily(await res.json());
    } catch (err) {
      console.warn("[NEXUS PULSE] daily.json fallback:", err);
      applyDaily(FALLBACK_DAILY);
    }
  }

  async function loadDeals() {
    try {
      const res = await fetch("./data/deals.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      renderDeals(await res.json());
    } catch (err) {
      console.warn("[NEXUS PULSE] deals.json fallback:", err);
      renderDeals(FALLBACK_DEALS);
    }
  }

  function fillToolSelects() {
    const opts = GAMES.map((g) => `<option value="${g.id}">${g.title}</option>`).join("");
    const fps = $("#fpsGame");
    if (fps) fps.innerHTML = opts;
    const specs = $("#specsGame");
    if (specs) specs.innerHTML = GAMES.filter((g) => SPECS[g.id]).map((g) => `<option value="${g.id}">${g.title}</option>`).join("");
  }

  function estimateFps(gameId, gpu, cpu) {
    const game = GAMES.find((g) => g.id === gameId);
    if (!game) return 0;
    return Math.max(25, Math.min(360, Math.round((BASE_FPS * GPU_MULT[gpu] * CPU_MULT[cpu]) / game.demand)));
  }

  $("#fpsCalcBtn")?.addEventListener("click", () => {
    const gameId = $("#fpsGame").value;
    const fps = estimateFps(gameId, $("#fpsGpu").value, $("#fpsCpu").value);
    const game = GAMES.find((g) => g.id === gameId);
    $("#fpsResult").hidden = false;
    $("#fpsValue").textContent = fps;
    let note = "Ориентир для 1080p High.";
    if (fps >= 144) note = `Отлично для киберспорта в ${game.title}.`;
    else if (fps >= 60) note = `Комфортно для ${game.title} на высоких (1080p).`;
    else note = "Будет тяжеловато. Снижай пресеты или апгрейди GPU.";
    $("#fpsNote").textContent = note;
  });

  $("#specsBtn")?.addEventListener("click", () => {
    const spec = SPECS[$("#specsGame").value];
    if (!spec) return;
    $("#specsResult").hidden = false;
    $("#specsMin").innerHTML = spec.min.map((s) => `<li>${s}</li>`).join("");
    $("#specsRec").innerHTML = spec.rec.map((s) => `<li>${s}</li>`).join("");
  });

  function renderWishlist() {
    const list = $("#wishlist");
    const empty = $("#wishlistEmpty");
    if (!list) return;
    const items = getWishlist().map((id) => GAMES.find((g) => g.id === id)).filter(Boolean);
    if (empty) empty.hidden = items.length > 0;
    list.innerHTML = items.map((g) => `
      <li><span>${g.title}</span>
      <button type="button" data-remove="${g.id}" aria-label="Remove">✕</button></li>`).join("");
  }

  $("#wishlist")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-remove]");
    if (!btn) return;
    setWishlist(getWishlist().filter((id) => id !== btn.dataset.remove));
    renderWishlist();
    renderGames();
  });
  $("#clearWishlist")?.addEventListener("click", () => {
    setWishlist([]);
    renderWishlist();
    renderGames();
  });

  /* ---------- Speed test ---------- */
  const SPEED_CHUNKS = [
    { bytes: 100000, label: "100 KB" },
    { bytes: 1000000, label: "1 MB" },
    { bytes: 5000000, label: "5 MB" },
    { bytes: 10000000, label: "10 MB" },
  ];
  function cloudflareDownUrl(bytes) {
    return `https://speed.cloudflare.com/__down?bytes=${bytes}`;
  }

  async function measureLatency(rounds = 5) {
    const samples = [];
    for (let i = 0; i < rounds; i++) {
      const url = cloudflareDownUrl(0) + `&r=${Date.now()}-${i}`;
      const t0 = performance.now();
      try {
        await fetch(url, { cache: "no-store", mode: "cors" });
        samples.push(performance.now() - t0);
      } catch {
        try {
          const t1 = performance.now();
          await new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve();
            img.onerror = () => reject(new Error("img"));
            img.src = `https://www.cloudflare.com/favicon.ico?_=${Date.now()}-${i}`;
          });
          samples.push(performance.now() - t1);
        } catch { /* skip */ }
      }
    }
    if (!samples.length) throw new Error("latency-failed");
    samples.sort((a, b) => a - b);
    const mid = samples.slice(0, Math.max(1, Math.ceil(samples.length * 0.6)));
    return mid.reduce((a, b) => a + b, 0) / mid.length;
  }

  async function measureDownload(onProgress) {
    const speeds = [];
    for (let i = 0; i < SPEED_CHUNKS.length; i++) {
      const chunk = SPEED_CHUNKS[i];
      onProgress?.(i + 1, SPEED_CHUNKS.length, chunk.label);
      const url = cloudflareDownUrl(chunk.bytes) + `&r=${Date.now()}`;
      const t0 = performance.now();
      const res = await fetch(url, { cache: "no-store", mode: "cors" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const buf = await res.arrayBuffer();
      const dt = performance.now() - t0;
      if (dt < 8) continue;
      speeds.push((buf.byteLength * 8) / (dt / 1000) / 1e6);
    }
    if (!speeds.length) throw new Error("download-failed");
    const weight = speeds.map((_, idx) => idx + 1);
    const sumW = weight.reduce((a, b) => a + b, 0);
    return speeds.reduce((acc, s, i) => acc + s * weight[i], 0) / sumW;
  }

  function rateConnection(mbps, latencyMs) {
    if (mbps >= 50 && latencyMs <= 40) return { key: "excellent", cls: "rate-ok" };
    if (mbps >= 20 && latencyMs <= 80) return { key: "ok", cls: "rate-mid" };
    return { key: "weak", cls: "rate-bad" };
  }

  let speedBusy = false;
  async function runSpeedTest() {
    if (speedBusy) return;
    speedBusy = true;
    const btn = $("#speedBtn");
    const prog = $("#speedProgress");
    const result = $("#speedResult");
    const err = $("#speedError");
    if (err) { err.hidden = true; err.textContent = ""; }
    if (result) result.hidden = true;
    if (prog) { prog.hidden = false; prog.textContent = t("speed.progress"); }
    if (btn) { btn.disabled = true; btn.textContent = t("speed.progress"); }
    try {
      const latency = await measureLatency(5);
      if (prog) prog.textContent = `${t("speed.progress")} · ${t("speed.download")}`;
      const mbps = await measureDownload((step, total, label) => {
        if (prog) prog.textContent = `${t("speed.progress")} ${step}/${total} (${label})`;
      });
      const rating = rateConnection(mbps, latency);
      if (result) result.hidden = false;
      const dl = $("#speedDownload");
      const lat = $("#speedLatency");
      const rate = $("#speedRating");
      if (dl) dl.textContent = mbps.toFixed(1);
      if (lat) lat.textContent = String(Math.round(latency));
      if (rate) {
        rate.textContent = t("speed." + rating.key);
        rate.className = "speed-rating " + rating.cls;
      }
      lastNetworkLatency = latency;
      if (window.NexusPulse) window.NexusPulse.lastLatency = latency;
    } catch (e) {
      console.warn("[NEXUS PULSE] speed test failed:", e);
      if (err) { err.hidden = false; err.textContent = t("speed.err"); }
    } finally {
      speedBusy = false;
      if (prog) prog.hidden = true;
      if (btn) { btn.disabled = false; btn.textContent = t("speed.again"); }
    }
  }
  $("#speedBtn")?.addEventListener("click", runSpeedTest);

  /* ---------- Language switcher ---------- */
  let gtReady = false;
  let gtLoading = false;

  function applyFirstClassI18n() {
    const dict = I18N[currentLangBase()] || I18N.ru;
    $$("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (dict[key]) el.textContent = dict[key];
    });
    $$("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (dict[key]) el.setAttribute("placeholder", dict[key]);
    });
    document.documentElement.lang = currentLangCode().split("-")[0];
    const label = $("#langCurrent");
    if (label) {
      const code = currentLangCode();
      const found = WORLD_LANGS.find((x) => x[0] === code || x[0].startsWith(code));
      label.textContent = found ? found[1] : code.toUpperCase();
    }
  }

  function hideGoogleBanner() {
    if ($("#np-hide-gt")) return;
    const style = document.createElement("style");
    style.id = "np-hide-gt";
    style.textContent = `.goog-te-banner-frame,.goog-te-balloon-frame,#goog-gt-tt,.goog-tooltip,.goog-text-highlight{display:none!important;visibility:hidden!important}body{top:0!important}.skiptranslate,.goog-te-gadget{display:none!important}#google_translate_element{position:absolute;left:-9999px;height:0;overflow:hidden}`;
    document.head.appendChild(style);
  }

  function triggerGoogleTranslate(langCode) {
    hideGoogleBanner();
    const combo = document.querySelector(".goog-te-combo");
    if (!combo) return false;
    const mapped = langCode === "zh" ? "zh-CN" : langCode;
    combo.value = mapped;
    combo.dispatchEvent(new Event("change"));
    return true;
  }

  function clearGoogleTranslate() {
    const combo = document.querySelector(".goog-te-combo");
    if (combo) { combo.value = ""; combo.dispatchEvent(new Event("change")); }
    document.cookie = "googtrans=;path=/;max-age=0";
    document.cookie = "googtrans=;path=/;domain=" + location.hostname + ";max-age=0";
  }

  function loadGoogleTranslate(cb) {
    if (gtReady) { cb?.(); return; }
    if (gtLoading) {
      const wait = setInterval(() => { if (gtReady) { clearInterval(wait); cb?.(); } }, 200);
      return;
    }
    gtLoading = true;
    hideGoogleBanner();
    window.googleTranslateElementInit = function () {
      try {
        new google.translate.TranslateElement({
          pageLanguage: "ru",
          autoDisplay: false,
          layout: google.translate.TranslateElement.InlineLayout.HORIZONTAL,
        }, "google_translate_element");
      } catch (e) { console.warn("[NEXUS PULSE] GT init:", e); }
      gtReady = true;
      gtLoading = false;
      setTimeout(() => cb?.(), 400);
    };
    if (!document.getElementById("np-gt-script")) {
      const s = document.createElement("script");
      s.id = "np-gt-script";
      s.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
      s.async = true;
      s.onerror = () => { gtLoading = false; console.warn("[NEXUS PULSE] GT script blocked"); };
      document.body.appendChild(s);
    }
  }

  function closeLangPanel() {
    const panel = $("#langPanel");
    if (panel) panel.hidden = true;
    $("#langToggle")?.setAttribute("aria-expanded", "false");
  }

  function setLanguage(code) {
    localStorage.setItem(LANG_KEY, code);
    applyFirstClassI18n();
    wireDiscord();
    const dealsUpdated = $("#dealsUpdated");
    if (dealsUpdated && dealsUpdated.dataset.ts) {
      dealsUpdated.textContent = `${t("deals.updated")} ${formatUpdatedAt(dealsUpdated.dataset.ts)}`;
    }
    const newGamesUpdated = $("#newGamesUpdated");
    if (newGamesUpdated && newGamesUpdated.dataset.date) {
      newGamesUpdated.textContent = `${t("newGames.updated")} ${formatIsoDateRu(newGamesUpdated.dataset.date)}`;
    }
    const base = code.split("-")[0];
    const isFirstClass = FIRST_CLASS.includes(base) || code === "zh-CN" || code === "zh-TW";

    if (code === "ru" || (isFirstClass && base !== "zh" && code !== "zh-CN" && code !== "zh-TW")) {
      /* First-class chrome via embedded dict; clear any prior GT layer */
      const wasTranslated = document.documentElement.className.indexOf("translated") !== -1;
      clearGoogleTranslate();
      if (wasTranslated) {
        location.reload();
        return;
      }
      closeLangPanel();
      return;
    }

    /* Any other world language (incl. zh variants): Google Translate layer */
    loadGoogleTranslate(() => {
      triggerGoogleTranslate(code === "zh" ? "zh-CN" : code);
      closeLangPanel();
    });
  }

  function renderLangLists(filter) {
    const q = (filter || "").trim().toLowerCase();
    const popular = $("#langPopular");
    const all = $("#langAll");
    const match = (code, name) => !q || code.toLowerCase().includes(q) || name.toLowerCase().includes(q);
    const current = currentLangCode();
    const mkBtn = (code, name) =>
      `<button type="button" class="lang-option ${code === current || (current.startsWith("zh") && code.startsWith("zh")) ? "active" : ""}" data-lang="${code}"><span class="lang-code">${code}</span><span class="lang-name">${name}</span></button>`;
    if (popular) {
      popular.innerHTML = POPULAR_LANGS.map((code) => {
        const row = WORLD_LANGS.find((x) => x[0] === code || x[0].startsWith(code));
        return row && match(row[0], row[1]) ? mkBtn(row[0], row[1]) : "";
      }).join("");
    }
    if (all) all.innerHTML = WORLD_LANGS.filter(([c, n]) => match(c, n)).map(([c, n]) => mkBtn(c, n)).join("");
  }

  function wireLanguageSwitcher() {
    const toggle = $("#langToggle");
    const panel = $("#langPanel");
    const search = $("#langSearch");
    toggle?.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = panel.hidden;
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      if (open) { renderLangLists(); search?.focus(); }
    });
    search?.addEventListener("input", () => renderLangLists(search.value));
    panel?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-lang]");
      if (!btn) return;
      setLanguage(btn.dataset.lang);
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".lang-switcher")) closeLangPanel();
    });
    applyFirstClassI18n();
    const saved = currentLangCode();
    if (saved && saved !== "ru") setTimeout(() => setLanguage(saved), 600);
  }


  /* ---------- Mood / time game picker ---------- */
  const MOOD_PROFILES = {
    chill:   { genres: ["инди", "симуляторы", "гонки", "RPG"], prefer: ["stardew", "ets2", "forza5", "balatro", "celeste", "outerwilds", "cities", "farming"], avoidMulti: false },
    compete: { genres: ["киберспорт", "FPS"], prefer: ["cs2", "valorant", "dota2", "lol", "r6", "rocket", "apex", "ow2"], avoidMulti: false },
    story:   { genres: ["RPG", "экшен", "хоррор"], prefer: ["bg3", "rdr2", "witcher3", "cp2077", "gow", "alanwake2", "persona5", "hogwarts"], avoidMulti: false },
    horror:  { genres: ["хоррор"], prefer: ["re4", "alanwake2", "deadspace", "phasmo", "lethal", "outlast", "reVillage"], avoidMulti: false },
    coop:    { genres: ["хоррор", "экшен", "MMO", "киберспорт"], prefer: ["lethal", "phasmo", "gtav", "fortnite", "apex", "destiny2", "mhwilds", "wow"], avoidMulti: false },
    grind:   { genres: ["RPG", "MMO", "симуляторы"], prefer: ["diablo4", "poe2", "wow", "ffxiv", "lostark", "destiny2", "vampire", "newworld"], avoidMulti: false },
  };

  const MULTI_IDS = new Set([
    "cs2","valorant","dota2","lol","r6","rocket","fortnite","apex","ow2","codmw","destiny2",
    "gtav","wow","gw2","eso","lostark","newworld","throne","ffxiv","phasmo","lethal","outlast",
    "diablo4","poe2","mhwilds","forza5","f1_24","halo","r6","fortnite"
  ]);
  const SOLO_FRIENDLY = new Set([
    "elden","bg3","witcher3","cp2077","rdr2","skyrim","persona5","gow","spiderman2","totk","sekiro",
    "wukong","hollow","hades","celeste","stardew","balatro","outerwilds","re4","alanwake2","deadspace",
    "civ6","xcom2","ck3","stellaris","rimworld","ets2","msfs","doom","ultrakill","titanfall2","hogwarts","acvalhalla"
  ]);
  const SHORT_OK = new Set([
    "cs2","valorant","rocket","balatro","vampire","celeste","hades","ultrakill","ow2","apex","fortnite","lethal","phasmo"
  ]);
  const BINGE_OK = new Set([
    "bg3","elden","rdr2","witcher3","cp2077","skyrim","persona5","civ6","ck3","stellaris","wow","ffxiv","hogwarts","totk","acvalhalla","msfs"
  ]);

  let moodState = { mood: "chill", time: "short", mode: "any" };

  function wireMoodChips(containerSel, dataAttr, stateKey) {
    const root = $(containerSel);
    if (!root) return;
    root.addEventListener("click", (e) => {
      const btn = e.target.closest(`[${dataAttr}]`);
      if (!btn) return;
      root.querySelectorAll(".mood-chip").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      moodState[stateKey] = btn.getAttribute(dataAttr);
    });
  }

  function scoreGameForMood(g) {
    const profile = MOOD_PROFILES[moodState.mood] || MOOD_PROFILES.chill;
    let score = 0;
    if (profile.genres.includes(g.genre)) score += 4;
    if (profile.prefer.includes(g.id)) score += 6;
    if (moodState.mode === "multi") {
      if (MULTI_IDS.has(g.id) || g.genre === "киберспорт" || g.genre === "MMO") score += 5;
      else score -= 4;
    } else if (moodState.mode === "solo") {
      if (SOLO_FRIENDLY.has(g.id) || ["RPG", "инди", "стратегия", "хоррор", "экшен"].includes(g.genre)) score += 4;
      if (MULTI_IDS.has(g.id) && !SOLO_FRIENDLY.has(g.id)) score -= 3;
    }
    if (moodState.time === "short") {
      if (SHORT_OK.has(g.id) || g.genre === "киберспорт" || g.genre === "инди") score += 3;
      if (BINGE_OK.has(g.id)) score -= 2;
    } else if (moodState.time === "hour") {
      score += 1;
      if (SHORT_OK.has(g.id) || g.genre === "FPS") score += 2;
    } else if (moodState.time === "long" || moodState.time === "binge") {
      if (BINGE_OK.has(g.id) || g.genre === "RPG" || g.genre === "стратегия" || g.genre === "MMO") score += 4;
      if (SHORT_OK.has(g.id) && moodState.time === "binge") score -= 1;
    }
    score += g.rating / 5;
    return score;
  }

  function moodReason(g) {
    const bits = [];
    const profile = MOOD_PROFILES[moodState.mood];
    if (profile && profile.prefer.includes(g.id)) bits.push("точно в настроение");
    else if (profile && profile.genres.includes(g.genre)) bits.push(`жанр «${g.genre}»`);
    if (moodState.time === "short" && SHORT_OK.has(g.id)) bits.push("короткая сессия");
    if (moodState.time === "binge" && BINGE_OK.has(g.id)) bits.push("на весь вечер");
    if (moodState.mode === "multi" && MULTI_IDS.has(g.id)) bits.push("мультиплеер");
    if (moodState.mode === "solo" && SOLO_FRIENDLY.has(g.id)) bits.push("отлично соло");
    if (!bits.length) bits.push(`рейтинг ${g.rating.toFixed(1)}`);
    return bits.slice(0, 2).join(" · ");
  }

  function pickMoodGames() {
    const ranked = GAMES
      .map((g) => ({ g, score: scoreGameForMood(g) }))
      .sort((a, b) => b.score - a.score || b.g.rating - a.g.rating);
    const top = ranked.filter((x) => x.score > 0).slice(0, 3);
    const picks = (top.length >= 3 ? top : ranked.slice(0, 3)).map((x) => x.g);
    // diversify: if duplicates of same genre dominate, swap 3rd
    if (picks.length === 3 && picks[0].genre === picks[1].genre && picks[1].genre === picks[2].genre) {
      const alt = ranked.find((x) => x.g.genre !== picks[0].genre && !picks.includes(x.g));
      if (alt) picks[2] = alt.g;
    }
    return picks;
  }

  function renderMoodResults(picks) {
    const box = $("#moodResults");
    if (!box) return;
    box.hidden = false;
    box.innerHTML = picks.map((g, i) => `
      <article class="mood-result-card">
        <div class="mood-rank">#${i + 1}</div>
        <div class="mood-result-body">
          <h4>${g.title}</h4>
          <p class="mood-result-meta">${g.genre} · ★ ${g.rating.toFixed(1)} · ${g.platforms.join(", ")}</p>
          <p class="mood-result-why"><span data-i18n-skip>${t("mood.why")}</span> ${moodReason(g)}</p>
          <p class="mood-result-desc">${g.desc}</p>
        </div>
        <a class="btn btn-ghost btn-sm" href="#games" data-scroll-game="${g.id}">В каталог</a>
      </article>`).join("");
  }

  function wireMoodPicker() {
    wireMoodChips("#moodChips", "data-mood", "mood");
    wireMoodChips("#timeChips", "data-time", "time");
    wireMoodChips("#modeChips", "data-mode", "mode");
    $("#moodPickBtn")?.addEventListener("click", () => {
      const picks = pickMoodGames();
      renderMoodResults(picks);
      const btn = $("#moodPickBtn");
      if (btn) btn.textContent = t("mood.again");
    });
    $("#moodResults")?.addEventListener("click", (e) => {
      const a = e.target.closest("[data-scroll-game]");
      if (!a) return;
      // highlight search
      const id = a.getAttribute("data-scroll-game");
      const game = GAMES.find((g) => g.id === id);
      if (game && $("#gameSearch")) {
        $("#gameSearch").value = game.title;
        searchQuery = game.title;
        activeGenre = "all";
        $$("#genreFilters .chip").forEach((c) => c.classList.toggle("active", c.dataset.genre === "all"));
        renderGames();
      }
    });
  }


  function updateHeroStats() {
    const g = $("#statGames");
    const guides = $("#statGuides");
    const tools = $("#statTools");
    if (g) g.textContent = String(GAMES.length) + "+";
    if (guides) guides.textContent = String(GUIDES.length) + "+";
    if (tools) tools.textContent = "12";
  }

  /* ---------- Init ---------- */
  wireDiscord();
  wireLanguageSwitcher();
  updateHeroStats();
  renderGames();
  renderGuides();
  renderFact();
  renderGlossary();
  renderEsports();
  fillToolSelects();
  renderWishlist();
  wireMoodPicker();
  loadDaily();

  document.addEventListener("click", (e) => {
    const closeEl = e.target.closest("[data-close-modal]");
    if (closeEl) { closeContentModal(); return; }

    const guideBtn = e.target.closest("[data-guide-index]");
    if (guideBtn) {
      openGuide(Number(guideBtn.dataset.guideIndex));
      return;
    }

    const tip = e.target.closest("[data-tip-index]");
    if (tip) {
      const list = $("#tipsList");
      let tips = [];
      try { tips = JSON.parse(list?.dataset.tips || "[]"); } catch { tips = []; }
      const text = tips[Number(tip.dataset.tipIndex)] || tip.querySelector(".tip-text")?.textContent || "";
      openContentModal({
        kicker: "Горячий совет",
        title: "Совет дня",
        bodyHtml: `<p>${text}</p><p>Сохрани себе или кинь тиммейтам в Discord #гайды.</p>`,
        actionsHtml: `<button type="button" class="primary" data-close-modal>Закрыть</button>`,
      });
      return;
    }

    const deal = e.target.closest("[data-deal-url]");
    if (deal) {
      const url = deal.dataset.dealUrl;
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeContentModal();
    if (e.key === "Enter" || e.key === " ") {
      const tip = e.target.closest?.("[data-tip-index]");
      if (tip) { e.preventDefault(); tip.click(); }
      const deal = e.target.closest?.("[data-deal-url]");
      if (deal) { e.preventDefault(); deal.click(); }
    }
  });


  /* ---------- Bridge for features-extra.js ---------- */
  window.NexusPulse = {
    GAMES,
    SPECS,
    GPU_MULT,
    CPU_MULT,
    BASE_FPS,
    DISCORD_INVITE_URL,
    estimateFps,
    renderGames,
    renderDeals,
    renderWishlist,
    fillToolSelects,
    getWishlist,
    setWishlist,
    openContentModal,
    closeContentModal,
    updateHeroStats,
    t,
    get lastLatency() { return lastNetworkLatency; },
    set lastLatency(v) { lastNetworkLatency = v; },
    get activeGenre() { return activeGenre; },
    set activeGenre(v) { activeGenre = v; },
    get searchQuery() { return searchQuery; },
    set searchQuery(v) { searchQuery = v; },
    $,
    $$,
  };

  loadDeals();
})();
