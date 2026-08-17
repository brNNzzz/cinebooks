# -*- coding: utf-8 -*-
"""Tradução dos nomes de gênero (Ação, Drama, Comédia...) pros 11 idiomas do
site.

Diferente de título/sinopse (que vêm de fora, então cada filme guarda o
texto exatamente como veio da API), os GÊNEROS são um conjunto pequeno e
conhecido — a lista "oficial" de gêneros do TMDB tem só ~19 opções pra
filme e ~16 pra série, sempre as mesmas. Por isso dá pra ter uma tabela de
tradução fixa aqui, em vez de precisar buscar/cachear tradução por item
como fazemos com título/sinopse.

Como usar: `traduzir_genero(nome_do_genero, idioma_atual)` — devolve o nome
traduzido se reconhecer o gênero (em QUALQUER um dos 11 idiomas, já que um
"Gênero" no banco pode ter sido cadastrado em qualquer idioma), ou devolve
o nome original sem alterar se não reconhecer (ex: gênero cadastrado à mão,
fora da lista padrão do TMDB) — assim nunca quebra nem esconde nada, só
traduz o que a gente sabe traduzir.
"""

GENEROS_TRADUCAO = {
    "action": {
        "pt": "Ação", "en": "Action", "zh": "动作", "hi": "एक्शन", "es": "Acción",
        "fr": "Action", "ar": "أكشن", "bn": "অ্যাকশন", "ru": "Боевик", "ur": "ایکشن", "id": "Aksi",
    },
    "adventure": {
        "pt": "Aventura", "en": "Adventure", "zh": "冒险", "hi": "रोमांच", "es": "Aventura",
        "fr": "Aventure", "ar": "مغامرة", "bn": "অ্যাডভেঞ্চার", "ru": "Приключения", "ur": "مہم جوئی", "id": "Petualangan",
    },
    "animation": {
        "pt": "Animação", "en": "Animation", "zh": "动画", "hi": "एनिमेशन", "es": "Animación",
        "fr": "Animation", "ar": "رسوم متحركة", "bn": "অ্যানিমেশন", "ru": "Мультфильм", "ur": "اینیمیشن", "id": "Animasi",
    },
    "comedy": {
        "pt": "Comédia", "en": "Comedy", "zh": "喜剧", "hi": "कॉमेडी", "es": "Comedia",
        "fr": "Comédie", "ar": "كوميديا", "bn": "কমেডি", "ru": "Комедия", "ur": "مزاحیہ", "id": "Komedi",
    },
    "crime": {
        "pt": "Crime", "en": "Crime", "zh": "犯罪", "hi": "अपराध", "es": "Crimen",
        "fr": "Crime", "ar": "جريمة", "bn": "অপরাধ", "ru": "Криминал", "ur": "جرم", "id": "Kriminal",
    },
    "documentary": {
        "pt": "Documentário", "en": "Documentary", "zh": "纪录", "hi": "वृत्तचित्र", "es": "Documental",
        "fr": "Documentaire", "ar": "وثائقي", "bn": "তথ্যচিত্র", "ru": "Документальный", "ur": "دستاویزی", "id": "Dokumenter",
    },
    "drama": {
        "pt": "Drama", "en": "Drama", "zh": "剧情", "hi": "ड्रामा", "es": "Drama",
        "fr": "Drame", "ar": "دراما", "bn": "নাটক", "ru": "Драма", "ur": "ڈرامہ", "id": "Drama",
    },
    "family": {
        "pt": "Família", "en": "Family", "zh": "家庭", "hi": "पारिवारिक", "es": "Familia",
        "fr": "Familial", "ar": "عائلي", "bn": "পারিবারিক", "ru": "Семейный", "ur": "خاندانی", "id": "Keluarga",
    },
    "fantasy": {
        "pt": "Fantasia", "en": "Fantasy", "zh": "奇幻", "hi": "फैंटेसी", "es": "Fantasía",
        "fr": "Fantastique", "ar": "خيال", "bn": "ফ্যান্টাসি", "ru": "Фэнтези", "ur": "فینٹسی", "id": "Fantasi",
    },
    "history": {
        "pt": "História", "en": "History", "zh": "历史", "hi": "इतिहास", "es": "Historia",
        "fr": "Histoire", "ar": "تاريخ", "bn": "ইতিহাস", "ru": "История", "ur": "تاریخ", "id": "Sejarah",
    },
    "horror": {
        "pt": "Terror", "en": "Horror", "zh": "恐怖", "hi": "हॉरर", "es": "Terror",
        "fr": "Horreur", "ar": "رعب", "bn": "ভৌতিক", "ru": "Ужасы", "ur": "ہارر", "id": "Horor",
    },
    "music": {
        "pt": "Música", "en": "Music", "zh": "音乐", "hi": "संगीत", "es": "Música",
        "fr": "Musique", "ar": "موسيقى", "bn": "সঙ্গীত", "ru": "Музыка", "ur": "موسیقی", "id": "Musik",
    },
    "mystery": {
        "pt": "Mistério", "en": "Mystery", "zh": "悬疑", "hi": "रहस्य", "es": "Misterio",
        "fr": "Mystère", "ar": "غموض", "bn": "রহস্য", "ru": "Детектив", "ur": "معمہ", "id": "Misteri",
    },
    "romance": {
        "pt": "Romance", "en": "Romance", "zh": "爱情", "hi": "रोमांस", "es": "Romance",
        "fr": "Romance", "ar": "رومانسي", "bn": "রোমান্স", "ru": "Мелодрама", "ur": "رومانوی", "id": "Roman",
    },
    "science_fiction": {
        "pt": "Ficção científica", "en": "Science Fiction", "zh": "科幻", "hi": "विज्ञान कथा", "es": "Ciencia ficción",
        "fr": "Science-Fiction", "ar": "خيال علمي", "bn": "কল্পবিজ্ঞান", "ru": "Фантастика", "ur": "سائنس فکشن", "id": "Fiksi Ilmiah",
    },
    "tv_movie": {
        "pt": "Cinema TV", "en": "TV Movie", "zh": "电视电影", "hi": "टीवी फिल्म", "es": "Película de TV",
        "fr": "Téléfilm", "ar": "فيلم تلفزيوني", "bn": "টিভি মুভি", "ru": "Телефильм", "ur": "ٹی وی فلم", "id": "Film TV",
    },
    "thriller": {
        "pt": "Suspense", "en": "Thriller", "zh": "惊悚", "hi": "थ्रिलर", "es": "Suspense",
        "fr": "Thriller", "ar": "إثارة", "bn": "থ্রিলার", "ru": "Триллер", "ur": "تھرلر", "id": "Thriller",
    },
    "war": {
        "pt": "Guerra", "en": "War", "zh": "战争", "hi": "युद्ध", "es": "Bélica",
        "fr": "Guerre", "ar": "حرب", "bn": "যুদ্ধ", "ru": "Военный", "ur": "جنگ", "id": "Perang",
    },
    "western": {
        "pt": "Faroeste", "en": "Western", "zh": "西部", "hi": "वेस्टर्न", "es": "Western",
        "fr": "Western", "ar": "غربي", "bn": "ওয়েস্টার্ন", "ru": "Вестерн", "ur": "ویسٹرن", "id": "Barat",
    },
    "action_adventure": {
        "pt": "Ação e Aventura", "en": "Action & Adventure", "zh": "动作冒险", "hi": "एक्शन और रोमांच", "es": "Acción y Aventura",
        "fr": "Action et Aventure", "ar": "أكشن ومغامرة", "bn": "অ্যাকশন ও অ্যাডভেঞ্চার", "ru": "Боевик и Приключения", "ur": "ایکشن اور مہم جوئی", "id": "Laga & Petualangan",
    },
    "kids": {
        "pt": "Infantil", "en": "Kids", "zh": "儿童", "hi": "बाल", "es": "Infantil",
        "fr": "Enfants", "ar": "أطفال", "bn": "শিশুতোষ", "ru": "Для детей", "ur": "بچوں کا", "id": "Anak-anak",
    },
    "news": {
        "pt": "Notícias", "en": "News", "zh": "新闻", "hi": "समाचार", "es": "Noticias",
        "fr": "Actualités", "ar": "أخبار", "bn": "সংবাদ", "ru": "Новости", "ur": "خبریں", "id": "Berita",
    },
    "reality": {
        "pt": "Reality", "en": "Reality", "zh": "真人秀", "hi": "रियलिटी", "es": "Reality",
        "fr": "Réalité", "ar": "واقعي", "bn": "রিয়েলিটি", "ru": "Реальное ТВ", "ur": "ریئلٹی", "id": "Realitas",
    },
    "sci_fi_fantasy": {
        "pt": "Ficção científica e fantasia", "en": "Sci-Fi & Fantasy", "zh": "科幻奇幻", "hi": "विज्ञान कथा और फैंटेसी", "es": "Ciencia ficción y fantasía",
        "fr": "Science-Fiction & Fantastique", "ar": "خيال علمي وخيال", "bn": "কল্পবিজ্ঞান ও ফ্যান্টাসি", "ru": "Фантастика и фэнтези", "ur": "سائنس فکشن اور فینٹسی", "id": "Fiksi Ilmiah & Fantasi",
    },
    "soap": {
        "pt": "Novela", "en": "Soap", "zh": "肥皂剧", "hi": "सोप", "es": "Telenovela",
        "fr": "Soap", "ar": "دراما اجتماعية", "bn": "সোপ", "ru": "Мыльная опера", "ur": "سوپ", "id": "Sinetron",
    },
    "talk": {
        "pt": "Talk Show", "en": "Talk", "zh": "脱口秀", "hi": "टॉक शो", "es": "Programa de entrevistas",
        "fr": "Talk-show", "ar": "حوار", "bn": "টক শো", "ru": "Ток-шоу", "ur": "ٹاک شو", "id": "Bincang-bincang",
    },
    "war_politics": {
        "pt": "Guerra e Política", "en": "War & Politics", "zh": "战争与政治", "hi": "युद्ध और राजनीति", "es": "Guerra y Política",
        "fr": "Guerre et Politique", "ar": "حرب وسياسة", "bn": "যুদ্ধ ও রাজনীতি", "ru": "Война и политика", "ur": "جنگ اور سیاست", "id": "Perang & Politik",
    },
}

# Índice reverso: nome (em qualquer um dos 11 idiomas, em minúsculo) -> chave
# canônica. Montado uma vez, quando o módulo é carregado.
_INDICE_REVERSO = {}
for _chave, _traducoes in GENEROS_TRADUCAO.items():
    for _nome in _traducoes.values():
        _INDICE_REVERSO[_nome.strip().lower()] = _chave


def traduzir_genero(nome, idioma_atual):
    """Devolve o nome do gênero traduzido pro idioma_atual, se reconhecer
    esse gênero (não importa em que idioma ele estava cadastrado). Se não
    reconhecer (gênero fora da lista padrão do TMDB), devolve o nome como
    já estava, sem alterar."""
    chave = _INDICE_REVERSO.get((nome or "").strip().lower())
    if not chave:
        return nome
    return GENEROS_TRADUCAO[chave].get(idioma_atual, nome)
