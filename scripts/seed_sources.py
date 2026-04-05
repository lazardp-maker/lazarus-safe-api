from app.db import get_connection, get_db_path


SOURCES = [
    # Surse naționale oficiale
    {"name": "Politia Romana", "source_type": "official", "base_url": "https://www.politiaromana.ro", "county": None, "city": None, "trust_level": 5, "is_active": 1},
    {"name": "DSU", "source_type": "official", "base_url": "https://www.dsu.mai.gov.ro", "county": None, "city": None, "trust_level": 5, "is_active": 1},
    {"name": "IGSU", "source_type": "official", "base_url": "https://www.igsu.ro", "county": None, "city": None, "trust_level": 5, "is_active": 1},
    {"name": "MAI", "source_type": "official", "base_url": "https://www.mai.gov.ro", "county": None, "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Agerpres", "source_type": "press", "base_url": "https://agerpres.ro", "county": None, "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Digi24", "source_type": "press", "base_url": "https://www.digi24.ro", "county": None, "city": None, "trust_level": 3, "is_active": 1},
    {"name": "Stirile ProTV", "source_type": "press", "base_url": "https://stirileprotv.ro", "county": None, "city": None, "trust_level": 3, "is_active": 1},
    {"name": "HotNews", "source_type": "press", "base_url": "https://hotnews.ro", "county": None, "city": None, "trust_level": 3, "is_active": 1},
    {"name": "Antena 3 CNN", "source_type": "press", "base_url": "https://www.antena3.ro", "county": None, "city": None, "trust_level": 3, "is_active": 1},

    # București / Ilfov
    {"name": "IPJ Bucuresti", "source_type": "official", "base_url": "https://b.politiaromana.ro", "county": "bucuresti", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "ISU Bucuresti-Ilfov", "source_type": "official", "base_url": "https://isubif.ro", "county": "bucuresti", "city": "bucuresti", "trust_level": 5, "is_active": 1},

    # Argeș
    {"name": "IPJ Arges", "source_type": "official", "base_url": "https://ag.politiaromana.ro", "county": "arges", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "ISU Arges", "source_type": "official", "base_url": "https://www.isuarges.ro", "county": "arges", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Politia Locala Pitesti", "source_type": "official", "base_url": "https://www.primariapitesti.ro", "county": "arges", "city": "pitesti", "trust_level": 4, "is_active": 1},
    {"name": "Ziarul Argesul", "source_type": "press", "base_url": "https://ziarulargesul.ro", "county": "arges", "city": None, "trust_level": 4, "is_active": 1},
    {"name": "Ancheta Online", "source_type": "press", "base_url": "https://anchetaonline.ro", "county": "arges", "city": None, "trust_level": 4, "is_active": 1},
    {"name": "Jurnalul de Arges", "source_type": "press", "base_url": "https://jurnaluldearges.ro", "county": "arges", "city": None, "trust_level": 4, "is_active": 1},
    {"name": "ePitesti", "source_type": "press", "base_url": "https://epitesti.ro", "county": "arges", "city": "pitesti", "trust_level": 4, "is_active": 1},

    # Alba
    {"name": "IPJ Alba", "source_type": "official", "base_url": "https://ab.politiaromana.ro", "county": "alba", "city": None, "trust_level": 5, "is_active": 1},

    # Arad
    {"name": "IPJ Arad", "source_type": "official", "base_url": "https://ar.politiaromana.ro", "county": "arad", "city": None, "trust_level": 5, "is_active": 1},

    # Bacău
    {"name": "IPJ Bacau", "source_type": "official", "base_url": "https://bc.politiaromana.ro", "county": "bacau", "city": None, "trust_level": 5, "is_active": 1},

    # Bihor
    {"name": "IPJ Bihor", "source_type": "official", "base_url": "https://bh.politiaromana.ro", "county": "bihor", "city": None, "trust_level": 5, "is_active": 1},

    # Bistrița-Năsăud
    {"name": "IPJ Bistrita-Nasaud", "source_type": "official", "base_url": "https://bn.politiaromana.ro", "county": "bistrita nasaud", "city": None, "trust_level": 5, "is_active": 1},

    # Botoșani
    {"name": "IPJ Botosani", "source_type": "official", "base_url": "https://bt.politiaromana.ro", "county": "botosani", "city": None, "trust_level": 5, "is_active": 1},

    # Brăila
    {"name": "IPJ Braila", "source_type": "official", "base_url": "https://br.politiaromana.ro", "county": "braila", "city": None, "trust_level": 5, "is_active": 1},

    # Brașov
    {"name": "IPJ Brasov", "source_type": "official", "base_url": "https://bv.politiaromana.ro", "county": "brasov", "city": None, "trust_level": 5, "is_active": 1},

    # Buzău
    {"name": "IPJ Buzau", "source_type": "official", "base_url": "https://bz.politiaromana.ro", "county": "buzau", "city": None, "trust_level": 5, "is_active": 1},

    # Călărași
    {"name": "IPJ Calarasi", "source_type": "official", "base_url": "https://cl.politiaromana.ro", "county": "calarasi", "city": None, "trust_level": 5, "is_active": 1},

    # Caraș-Severin
    {"name": "IPJ Caras-Severin", "source_type": "official", "base_url": "https://cs.politiaromana.ro", "county": "caras severin", "city": None, "trust_level": 5, "is_active": 1},

    # Cluj
    {"name": "IPJ Cluj", "source_type": "official", "base_url": "https://cj.politiaromana.ro", "county": "cluj", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Cluj24", "source_type": "press", "base_url": "https://cluj24.ro", "county": "cluj", "city": None, "trust_level": 4, "is_active": 1},

    # Constanța
    {"name": "IPJ Constanta", "source_type": "official", "base_url": "https://ct.politiaromana.ro", "county": "constanta", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Replica Online", "source_type": "press", "base_url": "https://www.replicaonline.ro", "county": "constanta", "city": None, "trust_level": 4, "is_active": 1},

    # Covasna
    {"name": "IPJ Covasna", "source_type": "official", "base_url": "https://cv.politiaromana.ro", "county": "covasna", "city": None, "trust_level": 5, "is_active": 1},

    # Dâmbovița
    {"name": "IPJ Dambovita", "source_type": "official", "base_url": "https://db.politiaromana.ro", "county": "dambovita", "city": None, "trust_level": 5, "is_active": 1},

    # Dolj
    {"name": "IPJ Dolj", "source_type": "official", "base_url": "https://dj.politiaromana.ro", "county": "dolj", "city": None, "trust_level": 5, "is_active": 1},

    # Galați
    {"name": "IPJ Galati", "source_type": "official", "base_url": "https://gl.politiaromana.ro", "county": "galati", "city": None, "trust_level": 5, "is_active": 1},

    # Giurgiu
    {"name": "IPJ Giurgiu", "source_type": "official", "base_url": "https://gr.politiaromana.ro", "county": "giurgiu", "city": None, "trust_level": 5, "is_active": 1},

    # Gorj
    {"name": "IPJ Gorj", "source_type": "official", "base_url": "https://gj.politiaromana.ro", "county": "gorj", "city": None, "trust_level": 5, "is_active": 1},

    # Harghita
    {"name": "IPJ Harghita", "source_type": "official", "base_url": "https://hr.politiaromana.ro", "county": "harghita", "city": None, "trust_level": 5, "is_active": 1},

    # Hunedoara
    {"name": "IPJ Hunedoara", "source_type": "official", "base_url": "https://hd.politiaromana.ro", "county": "hunedoara", "city": None, "trust_level": 5, "is_active": 1},

    # Ialomița
    {"name": "IPJ Ialomita", "source_type": "official", "base_url": "https://il.politiaromana.ro", "county": "ialomita", "city": None, "trust_level": 5, "is_active": 1},

    # Iași
    {"name": "IPJ Iasi", "source_type": "official", "base_url": "https://is.politiaromana.ro", "county": "iasi", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Ziarul de Iasi", "source_type": "press", "base_url": "https://www.ziaruldeiasi.ro", "county": "iasi", "city": None, "trust_level": 4, "is_active": 1},

    # Ilfov
    {"name": "IPJ Ilfov", "source_type": "official", "base_url": "https://if.politiaromana.ro", "county": "ilfov", "city": None, "trust_level": 5, "is_active": 1},

    # Maramureș
    {"name": "IPJ Maramures", "source_type": "official", "base_url": "https://mm.politiaromana.ro", "county": "maramures", "city": None, "trust_level": 5, "is_active": 1},

    # Mehedinți
    {"name": "IPJ Mehedinti", "source_type": "official", "base_url": "https://mh.politiaromana.ro", "county": "mehedinti", "city": None, "trust_level": 5, "is_active": 1},

    # Mureș
    {"name": "IPJ Mures", "source_type": "official", "base_url": "https://ms.politiaromana.ro", "county": "mures", "city": None, "trust_level": 5, "is_active": 1},

    # Neamț
    {"name": "IPJ Neamt", "source_type": "official", "base_url": "https://nt.politiaromana.ro", "county": "neamt", "city": None, "trust_level": 5, "is_active": 1},

    # Olt
    {"name": "IPJ Olt", "source_type": "official", "base_url": "https://ot.politiaromana.ro", "county": "olt", "city": None, "trust_level": 5, "is_active": 1},

    # Prahova
    {"name": "IPJ Prahova", "source_type": "official", "base_url": "https://ph.politiaromana.ro", "county": "prahova", "city": None, "trust_level": 5, "is_active": 1},

    # Sălaj
    {"name": "IPJ Salaj", "source_type": "official", "base_url": "https://sj.politiaromana.ro", "county": "salaj", "city": None, "trust_level": 5, "is_active": 1},

    # Satu Mare
    {"name": "IPJ Satu Mare", "source_type": "official", "base_url": "https://sm.politiaromana.ro", "county": "satu mare", "city": None, "trust_level": 5, "is_active": 1},

    # Sibiu
    {"name": "IPJ Sibiu", "source_type": "official", "base_url": "https://sb.politiaromana.ro", "county": "sibiu", "city": None, "trust_level": 5, "is_active": 1},

    # Suceava
    {"name": "IPJ Suceava", "source_type": "official", "base_url": "https://sv.politiaromana.ro", "county": "suceava", "city": None, "trust_level": 5, "is_active": 1},

    # Teleorman
    {"name": "IPJ Teleorman", "source_type": "official", "base_url": "https://tr.politiaromana.ro", "county": "teleorman", "city": None, "trust_level": 5, "is_active": 1},

    # Timiș
    {"name": "IPJ Timis", "source_type": "official", "base_url": "https://tm.politiaromana.ro", "county": "timis", "city": None, "trust_level": 5, "is_active": 1},
    {"name": "Opinia Timisoarei", "source_type": "press", "base_url": "https://www.opiniatimisoarei.ro", "county": "timis", "city": None, "trust_level": 4, "is_active": 1},

    # Tulcea
    {"name": "IPJ Tulcea", "source_type": "official", "base_url": "https://tl.politiaromana.ro", "county": "tulcea", "city": None, "trust_level": 5, "is_active": 1},

    # Vâlcea
    {"name": "IPJ Valcea", "source_type": "official", "base_url": "https://vl.politiaromana.ro", "county": "valcea", "city": None, "trust_level": 5, "is_active": 1},

    # Vaslui
    {"name": "IPJ Vaslui", "source_type": "official", "base_url": "https://vs.politiaromana.ro", "county": "vaslui", "city": None, "trust_level": 5, "is_active": 1},

    # Vrancea
    {"name": "IPJ Vrancea", "source_type": "official", "base_url": "https://vn.politiaromana.ro", "county": "vrancea", "city": None, "trust_level": 5, "is_active": 1},
]

INSERT_SQL = """
INSERT OR IGNORE INTO sources (
    name,
    source_type,
    base_url,
    county,
    city,
    trust_level,
    is_active
)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""


def main() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()

        rows = [
            (
                source["name"],
                source["source_type"],
                source["base_url"],
                source["county"],
                source["city"],
                source["trust_level"],
                source["is_active"],
            )
            for source in SOURCES
        ]

        cursor.executemany(INSERT_SQL, rows)
        conn.commit()

        cursor.execute("SELECT COUNT(*) AS total FROM sources")
        total = cursor.fetchone()["total"]

        print("sources seeded")
        print(f"total sources in db: {total}")
        print(f"db path: {get_db_path()}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()