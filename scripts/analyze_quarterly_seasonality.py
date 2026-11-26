"""Empirical 4-Quarter Seasonality & Per-Year Catalyst Analyzer (2011-2026) from us_equities.db + macro/treasury."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "database" / "us_equities.db"
TREASURY_CSV = PROJECT_ROOT / "portfolio" / "data" / "us_treasury_prices_daily.csv"
MACRO_CSV = PROJECT_ROOT / "data" / "processed" / "us_inflation_macro_monthly.csv"
OUT_JSON = PROJECT_ROOT / "data" / "processed" / "quarterly_seasonality_summary.json"
OUT_CSV = PROJECT_ROOT / "data" / "processed" / "quarterly_seasonality_matrix.csv"

FLAGSHIP_11 = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "AMD", "ORCL", "^GSPC"
]

NOTABLE_UNIVERSE = sorted(
    set(
        FLAGSHIP_11
        + [
            "NFLX", "INTC", "CSCO", "ADBE", "CRM", "QCOM", "TXN", "IBM", "MU", "AMAT", "LRCX",
            "TSM", "ASML", "ANET", "NOW", "SMCI", "PLTR",
            "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "V", "MA", "AXP", "PGR",
            "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "BMY", "GILD", "AMGN", "CAH",
            "WMT", "COST", "PG", "KO", "PEP", "MCD", "SBUX", "NKE", "HD", "LOW", "TGT", "KR", "CHD", "AZO",
            "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "HAL",
            "CAT", "DE", "BA", "GE", "HON", "UNP", "UPS", "FDX", "LMT", "RTX", "DAL", "UAL", "AAL", "ETN",
            "DIS", "CMCSA", "T", "VZ", "TMUS",
            "NEE", "DUK", "SO", "AEP", "D", "XEL", "CEG", "VST", "ED",
            "PLD", "AMT", "EQIX", "SPG", "O", "PSA", "DLR",
            "FCX", "NEM", "LIN", "APD", "SHW", "NUE", "GLD",
        ]
    )
)

QUARTER_THEMES: Dict[str, Dict[str, str]] = {
    "Q1": {
        "name": "Q1 (Januari - Maret) · Enterprise CapEx Reset & Foundry Orders vs Post-Holiday Digest",
        "bull_driver": "Pencairan anggaran baru Hyperscaler Data Center CapEx, pemesanan alat semikonduktor awal tahun (LRCX/TSM/NVDA + GTC Maret), lonjakan rilis pelanggan Q4 streaming (NFLX), serta akumulasi emas & anggaran pertahanan.",
        "bear_driver": "Post-holiday consumer & smartphone digestion (pemangkasan pesanan komponen iPhone AAPL pasca-Natal), kontraksi musiman anggaran iklan digital Q1 (GOOGL), cuci gudang ritel pakaian (NKE), dan profit-taking perbankan (GS/C).",
    },
    "Q2": {
        "name": "Q2 (April - Juni) · Enterprise June Fiscal Year-End & Pre-Prime Day vs Summer Energy Lull",
        "bull_driver": "Penutupan tahun fiskal 30 Juni Microsoft (MSFT enterprise quota flush) & Microsoft Build, akumulasi menjelang Amazon Prime Day (AMZN), dimulainya produksi chip paruh kedua (AVGO/ANET), dan pameran Computex (AMD).",
        "bear_driver": "Berakhirnya musim flu musim dingin menekan distribusi farmasi (CAH), pergeseran belanja konsumen dari supermarket (KR) ke liburan luar ruang, serta fenomena 'Sell in May' pada PC klasik (INTC) dan jasa migas (HAL/XOM).",
    },
    "Q3": {
        "name": "Q3 (Juli - September) · Pre-iPhone Launch & Back-to-School vs 'September Effect' Cyclical Dump",
        "bull_driver": "Siklus peluncuran iPhone baru setiap September & belanja Back-to-School Mac/iPad (AAPL naik 87.5%), puncak volume transaksi kartu perjalanan musim panas lintas negara (MA), dan belanja perlengkapan rumah/sekolah (COST/HD).",
        "bear_driver": "Post-summer travel cliff pada maskapai (AAL turun 75%), berakhirnya US summer driving season (HAL/XOM/CVX), jeda konstruksi tembaga (FCX), serta institutional de-risking & tutup buku reksa dana di bulan September.",
    },
    "Q4": {
        "name": "Q4 (Oktober - Desember) · Holiday Spending, Logistics & Window Dressing vs Safe-Haven Exit",
        "bull_driver": "Puncak transaksi belanja Black Friday/Cyber Monday/Natal (MA naik 93.8%, V 81.2%), lonjakan pengiriman paket & tiket liburan (FDX/DAL/AVGO FY-end November), serta institutional window dressing saham keuangan (BLK/JPM/BAC).",
        "bear_driver": "Pertengahan tahun fiskal Oracle (Q2 FY ORCL sepi pembaruan lisensi dibanding Mei), pengumuman panduan belanja modal (CapEx) tahun depan pada earnings Oktober (META), serta rotasi keluar dari safe-haven emas (GLD/NEM) ke saham beta tinggi.",
    },
}

# Verified historical macro + market regime narratives for all 64 year-quarters (2011 Q1 - 2026 Q4)
YEAR_QUARTER_EVENTS: Dict[int, Dict[int, Dict[str, str]]] = {
    2011: {
        1: {
            "headline": "Likuiditas QE2 The Fed & Lonjakan Komoditas Energi",
            "bull": "Program QE2 The Fed dan pemulihan manufaktur AS mendorong reli energi, industri alat berat, serta belanja IT awal tahun.",
            "bear": "Gangguan rantai pasok akibat gempa/tsunami Jepang Maret 2011 dan lonjakan harga minyak menekan margin ritel serta maskapai.",
        },
        2: {
            "headline": "Berakhirnya QE2 & Kekhawatiran Utang Yunani",
            "bull": "Rotasi institusi menuju kesehatan, barang konsumsi primer, dan perangkat lunak berarus kas stabil menjelang akhir QE2.",
            "bear": "Berakhirnya pembelian obligasi QE2 di bulan Juni serta eskalasi krisis utang Yunani memicu pelemahan saham keuangan dan siklikal.",
        },
        3: {
            "headline": "Downgrade Peringkat Utang AS (AAA ke AA+) & Krisis Eurozone",
            "bull": "Pelarian modal ke aset safe-haven emas (GLD) dan saham defensif berdividen tinggi saat yield Treasury 10Y anjlok 123 bps.",
            "bear": "Penurunan peringkat kredit AS oleh S&P pada Agustus 2011 dan ancaman gagal bayar perbankan Eropa memicu aksi jual tajam saham berbeta tinggi.",
        },
        4: {
            "headline": "Intervensi Likuiditas Bank Sentral Global & Reli Liburan",
            "bull": "Koordinasi likuiditas dolar oleh The Fed/ECB memicu rebound tajam saham industri, energi, dan pembayaran ritel liburan Q4.",
            "bear": "Pelepasan aset lindung nilai emas dan saham teknologi yang memberi panduan konservatif akibat resesi Eropa.",
        },
    },
    2012: {
        1: {
            "headline": "Operasi LTRO Bank Sentral Eropa & Pemulihan Perbankan/Tech",
            "bull": "Suntikan likuiditas LTRO Eropa meredakan risiko sistemik, mengangkat saham perbankan AS, semikonduktor, dan ekosistem Apple.",
            "bear": "Saham utilitas dan defensif tertinggal akibat rotasi agresif investor kembali ke aset berisiko (risk-on) di kuartal pertama.",
        },
        2: {
            "headline": "Krisis Perbankan Spanyol & Perlambatan Manufaktur Global",
            "bull": "Saham defensif telekomunikasi, kesehatan, dan ritel diskon bertahan menguat saat yield 10Y turun 56 bps ke 1.66%.",
            "bear": "Kekhawatiran bailout bank Spanyol dan perlambatan ekonomi Tiongkok memukul saham komoditas, energi, dan semikonduktor siklus.",
        },
        3: {
            "headline": "Peluncuran QE3 The Fed & Janji 'Whatever It Takes' ECB",
            "bull": "Pengumuman QE3 terbuka oleh The Fed (September) dan komitmen ECB mengangkat saham teknologi, kartu pembayaran, serta emas.",
            "bear": "Peringatan laba kargo global (FDX/INTC) dan pelemahan permintaan PC menekan saham logistik serta perangkat keras klasik.",
        },
        4: {
            "headline": "Ketidakpastian 'US Fiscal Cliff' Pajak & Anggaran",
            "bull": "Saham industri dan keuangan menguat selektif mengantisipasi kompromi anggaran Kongres menjelang akhir Desember.",
            "bear": "Aksi jual pajak keuntungan modal (tax-gain harvesting) sebelum kenaikan tarif pajak 2013 menekan saham pemenang seperti AAPL dan tech besar.",
        },
    },
    2013: {
        1: {
            "headline": "Resolusi Fiscal Cliff & Arus Masuk Ekuitas Awal Tahun",
            "bull": "Kesepakatan pajak awal Januari dan dukungan likuiditas QE3 memicu reli luas di sektor kesehatan, konsumsi, media, dan transportasi.",
            "bear": "Penurunan harga komoditas logam/emas dan pemangkasan pesanan komponen smartphone pasca-liburan menahan saham tambang serta rantai pasok.",
        },
        2: {
            "headline": "'Taper Tantrum' Bernanke & Lonjakan Yield Treasury +63 bps",
            "bull": "Kenaikan yield 10Y dari 1.85% ke 2.48% menguntungkan margin bunga perbankan (JPM/BAC) serta saham pemulihan konsumen AS.",
            "bear": "Sinyal pengurangan pembelian obligasi (tapering) oleh Ben Bernanke di Mei 2013 memukul keras emas (GLD/NEM), REIT, dan utilitas sensitif bunga.",
        },
        3: {
            "headline": "Penundaan Tapering September & Ekspansi Manufaktur Global",
            "bull": "Keputusan kejutan The Fed menunda tapering di September melambungkan saham industri dirgantara, semikonduktor, dan e-commerce.",
            "bear": "Saham ritel konvensional dan properti/telekomunikasi masih tertekan oleh level suku bunga KPR yang lebih tinggi dibanding awal tahun.",
        },
        4: {
            "headline": "Akselerasi PDB AS & Puncak Reli Tahun 2013",
            "bull": "Data pertumbuhan PDB AS di atas ekspektasi dan musim belanja akhir tahun yang solid mengangkat teknologi, perbankan, dan industri.",
            "bear": "Rotasi keluar dari saham defensif serta tekanan berkelanjutan pada tambang emas saat tapering resmi dimulai secara terukur di Desember.",
        },
    },
    2014: {
        1: {
            "headline": "Musim Dingin Ekstrem 'Polar Vortex' & Rotasi Value",
            "bull": "Cuaca dingin ekstrem meningkatkan permintaan utilitas listrik/gas dan distribusi kesehatan, ditambah pemesanan alat chip awal tahun.",
            "bear": "Pembekuan aktivitas ritel/penerbangan akibat Polar Vortex dan aksi ambil untung pada saham internet/bioteknologi bervaluasi tinggi.",
        },
        2: {
            "headline": "Gelombang M&A Korporasi & Ekspansi Cloud/Semikonduktor",
            "bull": "Turunnya yield 10Y ke 2.52% disertai gelombang akuisisi farmasi/teknologi mendorong kenaikan energi, semikonduktor, dan software cloud.",
            "bear": "Perbankan investasi tertekan denda regulasi dan rendahnya volatilitas trading, sementara ritel pakaian menghadapi persaingan harga.",
        },
        3: {
            "headline": "Penguatan Tajam Dolar AS & Awal Koreksi Komoditas",
            "bull": "Saham berorientasi domestik AS, kesehatan, dan peluncuran siklus layar besar iPhone 6 (AAPL) memimpin penguatan kuartal ketiga.",
            "bear": "Reli indeks Dolar AS (DXY) dan turunnya harga minyak mentah mulai memukul sektor energi (XOM/HAL) serta industri pengekspor.",
        },
        4: {
            "headline": "Kejatuhan Harga Minyak OPEC vs Ledakan Konsumen & Maskapai",
            "bull": "Anjloknya harga minyak mentah hingga ~40% menjadi pajak negatif bagi konsumen: saham maskapai (DAL/AAL), ritel, dan kartu pembayaran melesat.",
            "bear": "Keputusan OPEC mempertahankan produksi November 2014 memicu kejatuhan tajam saham minyak dan jasa pengeboran (HAL/SLB/XOM/COP).",
        },
    },
    2015: {
        1: {
            "headline": "Dolar AS Kuat & Kejatuhan Laba Sektor Energi",
            "bull": "Belanja konsumen domestik, layanan kesehatan, dan ekspansi pelanggan streaming/e-commerce menguat di tengah bunga rendah.",
            "bear": "Penguatan Dolar AS menggerus pendapatan luar negeri emiten multinasional, diperberat anjloknya belanja modal hulu migas.",
        },
        2: {
            "headline": "Kebuntuan Utang Yunani & Kenaikan Yield Obligasi Global",
            "bull": "Perbankan AS menguat mengantisipasi kenaikan bunga The Fed, bersama platform iklan digital dan kesehatan (UNH).",
            "bear": "Kenaikan yield 10Y sebesar +40 bps menekan utilitas/REIT, sedangkan kelebihan pasokan minyak kembali menekan sektor energi dan transportasi.",
        },
        3: {
            "headline": "Devaluasi Yuan Tiongkok Agustus 2015 & Aksi Jual Global",
            "bull": "Hanya segelintir raksasa cloud/e-commerce (AMZN/GOOGL) dan utilitas defensif yang mampu bertahan positif di tengah guncangan pasar.",
            "bear": "Devaluasi mendadak mata uang Yuan Tiongkok memicu kepanikan deflasi global: komoditas tembaga (FCX), energi, chip, dan bioteknologi jatuh tajam.",
        },
        4: {
            "headline": "Dominasi Mega-Cap Tech & Kenaikan Bunga Pertama The Fed",
            "bull": "Kinerja impresif cloud dan iklan digital memicu reli akhir tahun sebelum The Fed menaikkan suku bunga 25 bps di Desember 2015.",
            "bear": "Harga minyak jatuh menembus di bawah $38/barel dan ritel departemen store tertekan cuaca musim dingin yang hangat.",
        },
    },
    2016: {
        1: {
            "headline": "Kepanikan Minyak $26/Barel Lalu Rebound Dovish The Fed",
            "bull": "Pernyataan dovish Janet Yellen menjatuhkan yield 10Y sebesar 48 bps ke 1.79%, memicu lonjakan emas (GLD/NEM), utilitas, dan dividen defensif.",
            "bear": "Kekhawatiran kredit energi di Januari-Februari memukul perbankan (BAC/GS/MS) serta saham teknologi bervaluasi tinggi.",
        },
        2: {
            "headline": "Kejutan Referendum Brexit Juni 2016 & Pemulihan Minyak",
            "bull": "Rebound harga minyak mentah ke ~$50 mengangkat sektor energi, sementara turunnya yield 10Y ke 1.49% menopang kesehatan, REIT, dan emas.",
            "bear": "Hasil pemungutan suara Brexit mengguncang saham perbankan global, maskapai penerbangan Eropa-Atlantik, dan rantai pasok smartphone.",
        },
        3: {
            "headline": "Stabilisasi Ekonomi Global & Kebangkitan Siklus Semikonduktor",
            "bull": "Meredanya efek Brexit dan lonjakan permintaan GPU/data center awal mendorong reli semikonduktor (NVDA/AMAT/LRCX), teknologi, dan bank.",
            "bear": "Rotasi keluar dari saham defensif (utilitas, telekomunikasi, real estat, dan supermarket) saat yield obligasi mulai berbalik naik.",
        },
        4: {
            "headline": "Reli Reflasi Pasca Pemilu AS November 2016 (Yield +84 bps)",
            "bull": "Ekspektasi pemotongan pajak, deregulasi, dan belanja infrastruktur melambungkan perbankan (GS/JPM/BAC), industri, maskapai, dan energi.",
            "bear": "Lonjakan tajam yield 10Y dari 1.61% ke 2.45% memukul keras emas (GLD/NEM), REIT, barang konsumsi primer, dan memicu rotasi keluar dari tech.",
        },
    },
    2017: {
        1: {
            "headline": "Sinkronisasi Pertumbuhan Global ('Goldilocks' Volatilitas Rendah)",
            "bull": "Pertumbuhan serentak ekonomi AS-Eropa-Asia tanpa lonjakan inflasi mengangkat teknologi mega-cap, semikonduktor, dan kesehatan.",
            "bear": "Harga minyak terkoreksi akibat naiknya produksi shale oil AS, menekan saham energi (XOM/HAL) dan operator telekomunikasi.",
        },
        2: {
            "headline": "Akselerasi Adopsi Cloud, E-Commerce & Peralatan Chip",
            "bull": "Rekor laba kuartalan raksasa cloud/platform digital, pembayaran elektronik, dan perawatan kesehatan mendorong kenaikan stabil.",
            "bear": "Ancaman disrupsi e-commerce (akuisisi Whole Foods oleh Amazon di Juni 2017) memukul ritel supermarket (KR/TGT) ditambah lemahnya harga minyak.",
        },
        3: {
            "headline": "Siklus Semikonduktor Memori/Fab & Pemulihan Komoditas",
            "bull": "Kekurangan pasokan chip memori global, peluncuran iPhone X, dan pemulihan harga minyak/tembaga mengangkat teknologi serta material.",
            "bear": "Bencana badai Harvey/Irma mengganggu operasional maskapai dan media hiburan tradisional tertekan tren pemutusan TV kabel (cord-cutting).",
        },
        4: {
            "headline": "Pengesahan UU Pemotongan Pajak Korporasi AS (TCJA 35% ke 21%)",
            "bull": "Pengesahan reformasi pajak korporasi AS di Desember 2017 memicu reli luas pada ritel domestik, perbankan, transportasi, dan teknologi.",
            "bear": "Emiten utilitas dan beberapa farmasi tertinggal karena manfaat pemotongan tarif pajak domestik lebih kecil atau kenaikan yield obligasi.",
        },
    },
    2018: {
        1: {
            "headline": "Lonjakan Volatilitas Februari ('Volmageddon') & Awal Tarif Dagang",
            "bull": "Pertumbuhan pesat layanan cloud enterprise (MSFT/ADBE/NFLX) dan belanja peralatan chip masih menopang sektor teknologi pilihan.",
            "bear": "Lonjakan upah Januari memicu kenaikan yield 10Y ke 2.74% dan meledaknya produk short-VIX, disusul pengumuman tarif baja/aluminium AS.",
        },
        2: {
            "headline": "Lonjakan Laba +25% Berkat Pajak TCJA & Reli Minyak Mentah",
            "bull": "Rekor buyback saham dari repatriasi kas pajak, penguatan e-commerce/ritel AS, serta naiknya harga minyak mengangkat energi (XOM/COP).",
            "bear": "Eskalasi tarif impor AS-Tiongkok dan penguatan Dolar AS menekan saham industri pengekspor (CAT/BA) serta perbankan.",
        },
        3: {
            "headline": "Puncak Ekspansi Ekonomi AS (AAPL Tembus Valuasi $1 Triliun)",
            "bull": "Pertumbuhan PDB AS di atas 3% mendorong AAPL menembus kapitalisasi $1 triliun bersama reli kuat sektor kesehatan (LLY/PFE/UNH) dan pembayaran.",
            "bear": "Perlambatan permintaan otomotif/tembaga Tiongkok akibat perang dagang dan kekhawatiran siklus puncak memori menekan chip (MU/INTC) serta FCX.",
        },
        4: {
            "headline": "Aksi Jual Hawkish The Fed ('Autopilot QT') & Perang Dagang",
            "bull": "Hanya saham defensif murni seperti utilitas listrik (ED/NEE), kebutuhan pokok (PG/KO/MCD), dan emas (GLD/NEM) yang naik sebagai pelindung nilai.",
            "bear": "Kenaikan suku bunga Desember The Fed di tengah perlambatan global dan kejatuhan minyak -38% menjatuhkan S&P 500 -14.0%, tech, dan energi.",
        },
    },
    2019: {
        1: {
            "headline": "Pivot Dovish The Fed (Pause Kenaikan Suku Bunga)",
            "bull": "Keputusan Jerome Powell menghentikan kenaikan bunga dan memangkas rencana QT memicu rebound tajam +13.1% dipimpin semikonduktor dan cloud.",
            "bear": "Kekhawatiran reformasi harga obat ('Medicare for All') menekan asuransi kesehatan/farmasi (UNH/PFE/CVS), serta krisis Boeing 737 MAX dimulai.",
        },
        2: {
            "headline": "Pasang-Surut Tarif AS-Tiongkok vs Ekspektasi Pemangkasan Bunga",
            "bull": "Turunnya yield 10Y sebesar 41 bps ke 2.00% mengangkat software enterprise (MSFT/SAP), kartu pembayaran (MA/V), dan emas.",
            "bear": "Ancaman tarif baru Mei 2019 dan pembatasan ekspor Huawei menekan rantai pasok chip eksposur Tiongkok serta sektor energi.",
        },
        3: {
            "headline": "Pemangkasan Suku Bunga 'Insurance Cuts' The Fed & Inversi Yield",
            "bull": "Dua kali pemangkasan bunga The Fed dan turunnya yield 10Y ke 1.68% menguntungkan properti REIT, utilitas, barang konsumsi, dan rantai pasok iPhone 11.",
            "bear": "Inversi kurva imbal hasil AS Agustus 2019 memicu kecemasan resesi yang menekan energi, material tembaga, dan kesehatan.",
        },
        4: {
            "headline": "Kesepakatan Dagang Fase-1 AS-Tiongkok & Likuiditas Repo The Fed",
            "bull": "Tercapainya kesepakatan dagang Fase-1 dan suntikan likuiditas repo The Fed melambungkan semikonduktor (AAPL/NVDA/AMD), perbankan, dan kesehatan.",
            "bear": "Saham defensif utilitas/REIT tertinggal saat yield berbalik naik 24 bps, sementara Boeing (BA) tertekan penghentian produksi 737 MAX.",
        },
    },
    2020: {
        1: {
            "headline": "Kepanikan Pandemi COVID-19 & Lockdown Ekonomi Global",
            "bull": "Hanya segelintir pemenang pandemi awal seperti streaming/cloud rumahan (NFLX/NVDA/AMZN) dan aset safe-haven emas (GLD) yang mencatatkan penguatan.",
            "bear": "Penghentian penerbangan, penutupan ritel, dan perang harga minyak Arab Saudi-Rusia menjatuhkan S&P 500 -20.0%, maskapai, energi, dan bank.",
        },
        2: {
            "headline": "Stimulus Fiskal CARES Act + QE Tak Terbatas The Fed (+20% Rebound)",
            "bull": "Suku bunga 0%, stimulus triliunan dolar, dan ledakan ekonomi digital Work-From-Home melambungkan saham tech, e-commerce, chip, dan renovasi rumah.",
            "bear": "Maskapai penerbangan, perbankan tradisional (pencadangan kredit macet tinggi), dan utilitas tertinggal jauh dari reli pemulihan teknologi.",
        },
        3: {
            "headline": "Akselerasi Adopsi Digital, Stock Split AAPL/TSLA & Pemulihan Logistik",
            "bull": "Lonjakan pengiriman paket e-commerce (FDX/UPS), permintaan perangkat kerja jarak jauh, dan pengumuman stock split AAPL/TSLA memicu reli kuat.",
            "bear": "Sektor energi (XOM/CVX/HAL) kembali terkoreksi akibat lemahnya permintaan bahan bakar jet/kantor, sementara perbankan tertekan NIM bunga 0%.",
        },
        4: {
            "headline": "Terobosan Vaksin mRNA COVID-19 (Rotasi Besar 'Reopening Trade')",
            "bull": "Pengumuman efikasi >90% vaksin Pfizer/Moderna di November 2020 memicu lonjakan saham perbankan, energi, maskapai (DAL), industri, dan semikonduktor.",
            "bear": "Investor melepas emas (GLD/NEM) dan melakukan rotasi keluar dari sebagian saham defensif 'stay-at-home' menuju sektor siklikal pembukaan ekonomi.",
        },
    },
    2021: {
        1: {
            "headline": "Stimulus Fiskal $1.9T, Vaksinasi Massal & Lonjakan Yield +83 bps",
            "bull": "Pembukaan kembali ekonomi dan lonjakan yield 10Y dari 0.92% ke 1.75% melambungkan energi (XOM/HAL), perbankan (JPM/BAC/GS), alat berat, dan peralatan chip.",
            "bear": "Kenaikan cepat suku bunga obligasi menekan valuasi saham growth berdurasi panjang, emas (GLD/NEM), serta memicu pencernaan saham pemenang WFH 2020.",
        },
        2: {
            "headline": "Ledakan Laba Raksasa Teknologi & Penurunan Kembali Yield 10Y",
            "bull": "Turunnya kembali yield 10Y sebesar 30 bps ke 1.44% berpadu dengan lonjakan laba iklan digital, cloud, dan GPU (NVDA/MSFT/GOOGL/META) memicu reli baru.",
            "bear": "Kekhawatiran biaya bahan baku/upah dan normalisasi pasca-pembukaan menekan maskapai (DAL/UAL) serta utilitas dan otomotif tertentu.",
        },
        3: {
            "headline": "Gelombang Varian Delta, Kemacetan Rantai Pasok & Krisis Evergrande",
            "bull": "Perangkat lunak langganan enterprise (MSFT/NOW/CRM) dan farmasi/vaksin bertahan naik di tengah ketidakpastian pertumbuhan.",
            "bear": "Gangguan pelabuhan/logistik global, pengetatan regulasi teknologi Tiongkok, dan gagal bayar Evergrande menekan industri, tembaga (FCX), serta kargo (FDX).",
        },
        4: {
            "headline": "Musim Liburan Kuat & Kelangkaan Chip meski The Fed Mulai Hawkish",
            "bull": "Daya harga (pricing power) kuat di tengah inflasi mengangkat semikonduktor (AVGO/NVDA/AMD/QCOM), peritel gudang (COST/HD), dan kesehatan.",
            "bear": "Kemunculan varian Omicron di akhir November dan sinyal percepatan tapering The Fed memukul saham perjalanan, pembayaran lintas negara, dan fintech.",
        },
    },
    2022: {
        1: {
            "headline": "Invasi Rusia ke Ukraina, Lonjakan Minyak >$100 & Siklus Hike The Fed",
            "bull": "Guncangan pasokan komoditas global melambungkan saham migas (XOM/CVX/OXY/HAL), pertahanan militer (LMT/RTX), tambang emas/tembaga, dan asuransi.",
            "bear": "Inflasi tinggi dan kenaikan bunga perdana The Fed (+82 bps pada yield 10Y) memicu kompresi valuasi tajam pada teknologi, streaming (NFLX), dan semikonduktor.",
        },
        2: {
            "headline": "Inflasi CPI ~9% & Kenaikan Agresif 75 bps The Fed (Bear Market)",
            "bull": "Hanya segelintir saham farmasi defensif berdividen (LLY/MRK/BMY/AT&T) yang mampu mencatatkan return positif sebagai tempat berlindung.",
            "bear": "Kenaikan suku bunga 75 bps dan kekhawatiran resesi menjatuhkan S&P 500 -16.5%: e-commerce, semikonduktor, bank investasi, dan kripto/growth anjlok dalam.",
        },
        3: {
            "headline": "Pidato Hawkish Powell di Jackson Hole & Yield 10Y Tembus 3.80%",
            "bull": "Ketahanan pengiriman musim gugur dan insentif energi bersih (IRA Agustus 2022) menopang segelintir saham energi/industri terpilih dan NFLX/TSLA.",
            "bear": "Penegasan Powell bahwa bunga akan ditahan tinggi demi menjinakkan inflasi mendorong yield 10Y +83 bps, menekan REIT, telekomunikasi, PC (INTC/AMD), dan properti.",
        },
        4: {
            "headline": "Inflasi CPI Melandai (Oktober) & Rebound Sektor Riil/Dow Jones",
            "bull": "Data CPI Oktober yang lebih sejuk memicu reli besar saham industri dirgantara (BA/GE/CAT/DE), energi (XOM/HAL), perbankan (JPM), dan kartu pembayaran (MA/V).",
            "bear": "Panduan belanja modal tinggi dan perlambatan cloud/iklan/EV menjatuhkan beberapa mega-cap tech (META, AMZN, TSLA, AAPL) berlawanan dengan penguatan indeks.",
        },
    },
    2023: {
        1: {
            "headline": "Euforia Awal Generative AI (ChatGPT) & Krisis Bank Regional SVB",
            "bull": "Peluncuran ChatGPT memicu gelombang akumulasi semikonduktor AI (NVDA +90%, AMD, META 'Year of Efficiency'), ditambah pelarian ke mega-cap tech & emas saat SVB kolaps.",
            "bear": "Kejatuhan Silicon Valley Bank (Maret 2023) memicu aksi jual tajam saham perbankan (BAC/WFC/SCHW), ditambah rotasi keluar dari kesehatan dan energi.",
        },
        2: {
            "headline": "Ledakan Panduan Chip AI NVIDIA (Mei 2023) & Resolusi Plafon Utang AS",
            "bull": "Revisi panduan pendapatan data center AI oleh NVDA yang melampaui konsensus hingga >50% mengangkat seluruh rantai pasok AI, cloud (MSFT/AMZN/AVGO), dan pelayaran/maskapai.",
            "bear": "Saham konsumsi primer, farmasi pasca-COVID (PFE/BMY), utilitas, dan energi tertinggal akibat tersedotnya arus dana ke reli teknologi AI.",
        },
        3: {
            "headline": "Narasi 'Higher-for-Longer' & Lonjakan Yield 10Y +75 bps ke 4.57%",
            "bull": "Kenaikan harga minyak produksi OPEC+ mengangkat sektor energi (XOM/HAL/COP), bersama ketahanan obat penurun berat badan GLP-1 (LLY) dan iklan digital (GOOGL/META).",
            "bear": "Lonjakan tajam yield Treasury 10Y ke 4.57% memukul keras utilitas listrik (NEE), REIT, maskapai (AAL/DAL akibat mahalnya avtur), dan ritel.",
        },
        4: {
            "headline": "Sinyal 'Fed Pivot' Desember 2023 (Yield 10Y Jatuh -71 bps ke 3.87%)",
            "bull": "Proyeksi pemangkasan bunga 2024 oleh The Fed memicu 'everything rally': semikonduktor (AVGO/AMD/INTC), perbankan (BAC/JPM/BLK), REIT, dan ritel liburan melesat.",
            "bear": "Turunnya harga minyak mentah di akhir tahun menekan sektor energi (XOM/CVX/HAL/SLB) sehingga bergerak berlawanan arah terhadap reli S&P 500 +11.2%.",
        },
    },
    2024: {
        1: {
            "headline": "Belanja Modal Klaster GPU AI Hyperscaler & Ketahanan Ekonomi AS",
            "bull": "Lonjakan pesanan infrastruktur AI, pembangkit listrik nuklir/data center (CEG/VST), obat GLP-1 (LLY), dan semikonduktor (NVDA/SMCI/MU) melambungkan indeks +10.2%.",
            "bear": "Penurunan pengiriman kendaraan listrik global menekan TSLA, masalah kualitas pesawat menekan Boeing (BA), dan penundaan pemangkasan bunga menekan REIT.",
        },
        2: {
            "headline": "Konsentrasi Ekstrem Semikonduktor AI, WWDC Apple Intelligence & Listrik AI",
            "bull": "Pengumuman Apple Intelligence di WWDC (AAPL), stock split NVDA/AVGO, dan kontrak listrik data center menopang penguatan mega-cap teknologi.",
            "bear": "Perlambatan anggaran software IT non-AI menekan enterprise SaaS (CRM/ADBE) serta saham industri alat berat dan konsumen berpendapatan menengah.",
        },
        3: {
            "headline": "Pemangkasan Bunga Perdana 50 bps The Fed & Unwind Yen Carry Trade",
            "bull": "Turunnya yield 10Y sebesar 54 bps ke 3.80% dan pemangkasan 50 bps The Fed di September melambungkan utilitas, properti REIT, perbankan, industri, dan emas.",
            "bear": "Pembongkaran Yen carry trade Agustus dan rotasi keluar dari semikonduktor bervaluasi tinggi memicu koreksi pada chip memori/peralatan fab (MU/AMAT/LRCX/ASML/INTC).",
        },
        4: {
            "headline": "Reli Pasca Pemilu AS November 2024 & Kenaikan Yield 10Y ke 4.57%",
            "bull": "Ekspektasi deregulasi perbankan/M&A dan adopsi custom AI ASIC melambungkan TSLA, AVGO, PLTR, perbankan besar (GS/WFC/JPM), dan maskapai (UAL/DAL).",
            "bear": "Lonjakan kembali yield 10Y +77 bps ke 4.57%, penguatan Dolar AS, dan kekhawatiran kebijakan kesehatan baru menekan farmasi (LLY/AMGN/UNH), material, dan REIT.",
        },
    },
    2025: {
        1: {
            "headline": "Guncangan Efisiensi AI DeepSeek & Volatilitas Tarif Perdagangan Awal Tahun",
            "bull": "Rotasi pelindung nilai mengalir deras ke emas (GLD/NEM), asuransi/kesehatan defensif (CVS/AMGN/JNJ/PGR), energi (XOM), dan kedirgantaraan/pertahanan Eropa-AS.",
            "bear": "Kemunculan model AI berbiaya rendah DeepSeek (Januari 2025) dan pengumuman tarif impor memicu koreksi valuasi tajam pada mega-cap AI/chip (NVDA/AVGO/TSLA/GOOGL).",
        },
        2: {
            "headline": "Penundaan Tarif Resiprokal April 2025 & Rebound Tajam CapEx AI (+10.6%)",
            "bull": "Jeda 90 hari tarif resiprokal AS pada April 2025 disertai konfirmasi naiknya belanja modal data center hyperscaler memicu lonjakan tajam semikonduktor, cloud (MSFT/ORCL), dan pembangkit listrik.",
            "bear": "Ketidakpastian biaya impor rantai pasok dan tekanan harga obat/MCR asuransi menahan sektor kesehatan (UNH/LLY/BMY) serta energi akibat naiknya kuota produksi OPEC+.",
        },
        3: {
            "headline": "Pemangkasan Suku Bunga Lanjutan The Fed & Siklus Peluncuran Hardware/AI Q3",
            "bull": "Pelonggaran moneter The Fed, peluncuran lini iPhone generasi baru (AAPL +24.3%), kemitraan cloud AI (ORCL/GOOGL), dan reli emas menopang kenaikan S&P 500 +7.8%.",
            "bear": "Perlambatan belanja konsumen restoran/minuman kemasan dan persaingan perangkat lunak menekan saham defensif konsumen serta SaaS tertentu (CRM/ADBE/COST).",
        },
        4: {
            "headline": "Ledakan Siklus Memori HBM AI vs Ambil Untung Server & Software Mahal",
            "bull": "Kelangkaan memori HBM untuk klaster AI tahun 2026 melambungkan MU (+70.8%) dan peralatan fab (LRCX), bersama rebound farmasi GLP-1 (LLY +41.1%) serta maskapai liburan.",
            "bear": "Aksi ambil untung akhir tahun dan kekhawatiran margin/belanja modal menekan perakit server AI (SMCI -38.9%), infrastruktur cloud berutang tinggi (ORCL -30.6%), dan META.",
        },
    },
    2026: {
        1: {
            "headline": "Koreksi Valuasi Awal Tahun 2026 & Kenaikan Yield 10Y ke 4.31%",
            "bull": "Kelanjutan supercycle memori/peralatan wafer fab, lonjakan harga energi/komoditas, dan rotasi ke saham nilai industri/pertahanan mencatat kenaikan kuat di tengah koreksi indeks.",
            "bear": "Pencernaan valuasi pasca-reli 2025, kenaikan yield 10Y +15 bps, dan lemahnya permintaan hardware konsumen awal tahun menekan S&P 500 -4.6% (AAPL -6.6%, software/cloud terkoreksi).",
        },
        2: {
            "headline": "Lonjakan Laba Korporasi Paruh Pertama & Ekspansi Jaringan AI (+14.9%)",
            "bull": "Laporan laba Q1-Q2 2026 yang melampaui ekspektasi memicu reli luas +14.9% dipimpin ekosistem perangkat keras/cloud, semikonduktor networking, keuangan, dan transportasi.",
            "bear": "Hanya sedikit saham defensif dan komoditas yang tertinggal atau terkoreksi tipis akibat perpindahan modal agresif ke saham pertumbuhan berbeta tinggi.",
        },
        3: {
            "headline": "Inflasi CPI Naik ke 3.72% & Lonjakan Tajam Yield Treasury 10Y +88 bps ke 5.29%",
            "bull": "Raksasa berarus kas bersih tinggi (net-cash mega-cap seperti AAPL +15.2% saat peluncuran produk September) dan perbankan diuntungkan oleh naiknya pendapatan bunga.",
            "bear": "Kenaikan Fed Funds ke 3.75% dan lonjakan yield 10Y menembus 5.29% memukul saham berutang tinggi, REIT, utilitas, serta industri siklikal sensitif pembiayaan.",
        },
        4: {
            "headline": "De-Risking Akhir Tahun pada Yield >5.0% (Data YTD s/d November 2026)",
            "bull": "Jaringan pembayaran transaksi liburan (MA +16.8%), raksasa perangkat keras kas tebal (AAPL +5.9%), dan utilitas/pertahanan pilihan bertahan hijau di tengah pasar yang terkoreksi.",
            "bear": "Bertahannya yield 10Y di atas 5.07% dan Fed Funds 3.88% memicu aksi de-risking portofolio akhir tahun (-4.3% pada S&P 500), menekan emas (GLD/NEM), software, dan aset spekulatif.",
        },
    },
}

SPECIFIC_REASONS: Dict[str, Dict[str, str]] = {
    "AAPL": {
        "Q1": "Turun di 56% tahun (Med -1.0%): Fase post-holiday iPhone demand digestion; puncak penjualan iPhone terjadi di Q4 lalu pesanan rantai pasok dipangkas di Jan-Feb.",
        "Q2": "Naik di 62% tahun (Mean +5.8%): Katalis konferensi developer tahunan WWDC (Juni) dan pengumuman fitur iOS/macOS baru.",
        "Q3": "Naik di 87.5% tahun (14/16 thn, Med +13.6%): Kuartal terkuat Apple berkat siklus peluncuran iPhone generasi baru setiap September & musim Back-to-School.",
        "Q4": "Naik di 75% tahun (Med +7.2%): Kuartal pengiriman puncak perangkat keras liburan Natal & Tahun Baru (Holiday Quarter).",
    },
    "MSFT": {
        "Q1": "Naik di 69% tahun (Med +6.4%): Penyerapan anggaran IT enterprise awal tahun kalender untuk lisensi cloud Azure.",
        "Q2": "Naik di 81.2% tahun (13/16 thn, Mean +8.7%): Tahun fiskal Microsoft berakhir 30 Juni (Q4 FY), memicu dorongan penutupan kontrak tahunan terbesar & konferensi MSFT Build.",
        "Q3": "Naik di 62% tahun (Mean +4.8%): Transisi awal tahun fiskal baru (Q1 FY) setelah lonjakan penutupan kontrak bulan Juni.",
        "Q4": "Naik di 69% tahun (Mean +6.4%): Pembelian lisensi enterprise akhir tahun kalender & reli teknologi Q4.",
    },
    "NVDA": {
        "Q1": "Naik di 81.2% tahun (13/16 thn, Mean +17.0%): Pencairan anggaran baru Hyperscaler Data Center CapEx, earnings Q4 FY akhir Februari, & konferensi tahunan NVIDIA GTC (Maret).",
        "Q2": "Naik di 69% tahun (Mean +15.3%, Med +12.4%): Pameran Computex (Mei/Juni) & ekspansi pengiriman GPU server paruh pertama.",
        "Q3": "Naik di 69% tahun (Mean +10.2%): Pengiriman arsitektur GPU menjelang instalasi klaster AI akhir tahun, meski dibayangi volatilitas September.",
        "Q4": "Naik di 69% tahun (Med +9.9%): Siklus belanja GPU gaming liburan & penutupan anggaran infrastruktur AI akhir tahun.",
    },
    "GOOGL": {
        "Q1": "Turun di 56.2% tahun (9/16 thn, Med -0.6%): Anggaran iklan digital global mengalami kontraksi musiman tajam di Jan-Mar setelah habis dikuras saat liburan Q4.",
        "Q2": "Naik di 62.5% tahun (Med +9.3%): Konferensi Google I/O (Mei) dan pemulihan belanja iklan merek menjelang musim panas.",
        "Q3": "Naik di 75.0% tahun (12/16 thn, Mean +7.8%): Penguncian inventaris iklan Back-to-School & persiapan kampanye Q4 di Search dan YouTube.",
        "Q4": "Naik di 62.5% tahun (Med +8.3%): Puncak pendapatan iklan e-commerce Black Friday & Cyber Monday.",
    },
    "AMZN": {
        "Q1": "Naik di 62.5% tahun (Mean +5.8%): Rilis angka penjualan liburan Q4 pada akhir Januari & efisiensi biaya pemenuhan awal tahun.",
        "Q2": "Naik di 87.5% tahun (14/16 thn, Mean +11.1%, Med +13.1%): Kuartal terbaik Amazon; akumulasi institusi menjelang Amazon Prime Day (Juli) & ekspansi AWS.",
        "Q3": "Naik di 62.5% tahun (Mean +5.5%): Realisasi transaksi Prime Day & belanja Back-to-School, diimbangi lonjakan biaya gudang pra-liburan.",
        "Q4": "Mean +3.5% (-1.2% di bawah S&P 500): Ekspektasi belanja liburan sudah di-price-in sejak Q2/Q3, ditambah lonjakan biaya logistik musiman Q4.",
    },
    "META": {
        "Q1": "Naik di 57% tahun (Mean +8.3%): Evaluasi efisiensi biaya tahunan & rilis kinerja iklan Q4 yang kuat di awal Februari.",
        "Q2": "Naik di 73.3% tahun (11/15 thn, Mean +8.8%): Peningkatan tarif iklan (CPM) musim semi & peluncuran produk iklan AI/Reels.",
        "Q3": "Naik di 60% tahun (Mean +9.3%): Konferensi Meta Connect (September) & akselerasi pemesanan iklan kuartal keempat.",
        "Q4": "Turun di 46.7% tahun (Mean +1.5%, -2.8% vs S&P): Pada earnings akhir Oktober, Meta rutin mengumumkan panduan kenaikan CapEx/OpEx tahun depan yang memicu aksi jual valuasi.",
    },
    "TSLA": {
        "Q1": "Turun di 50% tahun (Med -1.15%): Penurunan musiman pengiriman mobil di musim dingin & penyesuaian harga awal tahun.",
        "Q2": "Naik di 75.0% tahun (12/16 thn, Mean +25.3%, Med +14.2%): Rebound pengiriman kendaraan Q2, pembukaan pesanan musim semi, & hari pemegang saham tahunan.",
        "Q3": "Turun di 50% tahun (Med -1.40%): Penghentian sementara lini pabrik untuk upgrade model pada musim panas.",
        "Q4": "Naik di 62.5% tahun (Mean +12.8%): Dorongan pengiriman akhir tahun untuk mengejar target volume tahunan penuh.",
    },
    "AVGO": {
        "Q1": "Naik di 68.8% tahun (Med +11.9%): Momentum arus kas bebas & realisasi kenaikan dividen tahun fiskal baru.",
        "Q2": "Naik di 81.2% tahun (13/16 thn, Mean +12.9%): Siklus awal produksi komponen chip RF/wireless untuk perangkat baru paruh kedua.",
        "Q3": "Naik di 56.2% tahun (Mean +3.7%): Kuartal konsolidasi menjelang tutup buku tahun fiskal Broadcom di akhir Oktober.",
        "Q4": "Naik di 87.5% tahun (14/16 thn, Mean +14.2%, Med +15.8%): Tutup buku FY Broadcom (November); laporan Desember selalu membawa kenaikan dividen & panduan AI ASIC/networking.",
    },
    "AMD": {
        "Q1": "Naik di 56.2% tahun (Mean +8.9%): Pameran CES (Januari) & pembaruan peta jalan chip server/PC.",
        "Q2": "Naik di 62.5% tahun (Mean +23.5%, Med +16.0%): Katalis pameran Computex Taipei (Mei/Juni) & pesanan chip konsol/PC untuk paruh kedua.",
        "Q3": "Turun di 50% tahun (Med -1.70%): Koreksi musiman semikonduktor di bulan Agustus-September.",
        "Q4": "Naik di 62.5% tahun (Mean +11.1%): Peluncuran akselerator data center akhir tahun & reli semikonduktor Q4.",
    },
    "ORCL": {
        "Q1": "Naik di 56.2% tahun (Med +7.1%): Akumulasi menjelang penutupan tahun fiskal Oracle di musim semi.",
        "Q2": "Naik di 56.2% tahun (Mean +7.2%): Tahun fiskal Oracle berakhir 31 Mei (Q4 FY), memicu dorongan penutupan kontrak database & OCI terbesar.",
        "Q3": "Turun di 56.2% tahun (9/16 thn, Med -3.11%): Penurunan musiman penandatanganan lisensi enterprise selama liburan musim panas (Q1 FY Oracle).",
        "Q4": "Turun di 56.2% tahun (9/16 thn, Med -0.92%, -4.3% vs S&P): Pertengahan tahun fiskal Oracle (Q2 FY) yang secara historis paling lambat dibanding kuartal Mei.",
    },
    "^GSPC": {
        "Q1": "Naik di 68.8% tahun (Mean +2.26%, Med +3.36%): Arus masuk dana pensiun/401(k) awal tahun, diimbangi revisi panduan Q1.",
        "Q2": "Naik di 75.0% tahun (Mean +3.98%, Med +3.36%): Musim rilis laporan Q1 yang solid & buyback korporasi sebelum jeda musim panas.",
        "Q3": "Naik di 75.0% tahun namun Mean terendah (+1.29%): Likuiditas bursa tipis di Agustus & tekanan 'September Effect' (rebalancing reksa dana).",
        "Q4": "Naik di 81.2% tahun (13/16 thn, Mean +4.73%, Med +6.29%): Kuartal terkuat S&P 500 berkat belanja liburan, window dressing institusi, & Santa Claus Rally.",
    },
    "PGR": {"Q1": "Naik 87.5% (14/16 thn, Mean +11.3%): Siklus pembaruan polis asuransi kendaraan awal tahun & repricing premi Januari."},
    "CHD": {"Q1": "Naik 87.5% (14/16 thn, Mean +7.3%): Rotasi defensif awal tahun ke produk kebutuhan rumah tangga non-siklikal."},
    "GLD": {
        "Q1": "Naik 87.5% (14/16 thn, Mean +4.9%, Med +6.1%): Permintaan emas fisik Tahun Baru Imlek / Asia & rebalancing lindung nilai inflasi awal tahun.",
        "Q4": "Turun 50.0% (Mean -0.02%): Rotasi Risk-On akhir tahun; institusi melepas safe-haven emas untuk mengejar beta saham (window dressing Desember).",
    },
    "LRCX": {"Q1": "Naik 81.2% (13/16 thn, Med +12.7%): Front-loaded foundry wafer fab equipment orders di awal tahun kalender."},
    "NFLX": {"Q1": "Naik 75.0% (12/16 thn, Mean +21.4%, Med +18.3%): Rilis earnings Januari mencatat rekor tambahan pelanggan musim dingin/liburan Q4."},
    "CAH": {
        "Q1": "Naik 81.2% (13/16 thn, Med +7.3%): Puncak distribusi obat resep & vaksin selama musim flu musim dingin.",
        "Q2": "Turun 62.5% (10/16 thn, Med -1.8%): Penurunan musiman volume distribusi farmasi saat memasuki musim semi/panas.",
    },
    "LMT": {"Q1": "Naik 81.2% (13/16 thn, Mean +7.4%): Pencairan kontrak anggaran pertahanan tahunan AS (NDAA) di kuartal pertama."},
    "RTX": {
        "Q1": "Naik 81.2% (13/16 thn, Med +6.8%): Alokasi anggaran pertahanan awal tahun & pesanan komponen dirgantara.",
        "Q4": "Naik 87.5% (14/16 thn, Med +8.6%): Penyelesaian pengiriman kontrak militer akhir tahun anggaran.",
    },
    "GS": {"Q1": "Turun 68.8% (11/16 thn, Med -3.5%): Profit-taking pasca reli Q4 & reset akrual kompensasi/bonus tahunan bank investasi."},
    "NKE": {"Q1": "Turun 56.2% (9/16 thn, Mean -2.4%, Med -3.6%): Post-holiday inventory clearance & diskon cuci gudang pasca puncak belanja Q4."},
    "PFE": {"Q1": "Turun 56.2% (9/16 thn, Med -0.8%): Rotasi keluar dari farmasi dividen defensif menuju saham growth di awal tahun."},
    "DLR": {"Q2": "Naik 81.2% (13/16 thn, Med +6.7%): Penandatanganan sewa kapasitas data center hyperscale paruh pertama tahun."},
    "UNH": {"Q2": "Naik 81.2% (13/16 thn, Mean +7.4%): Kejelasan rasio biaya medis (MCR) tahun berjalan setelah kuartal flu musim dingin berlalu."},
    "NOW": {"Q2": "Naik 78.6% (11/14 thn, Mean +10.0%): Konferensi tahunan ServiceNow Knowledge (Mei) & gelombang pembaruan kontrak IT pertengahan tahun."},
    "ANET": {"Q2": "Naik 76.9% (10/13 thn, Med +13.3%): Pengiriman switch jaringan cloud AI 400G/800G untuk ekspansi data center musim panas."},
    "KR": {"Q2": "Turun 56.2% (9/16 thn, Mean -2.1%, Med -3.7%): Pergeseran belanja konsumen musim panas dari supermarket ke liburan & makan di luar."},
    "HAL": {
        "Q2": "Turun 56.2% (9/16 thn, Med -2.6%): Koreksi jasa ladang minyak setelah antisipasi musim semi.",
        "Q3": "Turun 68.8% (11/16 thn, Mean -3.7%, Med -6.6%): Berakhirnya US summer driving season pasca Labor Day & gangguan badai Teluk Meksiko.",
    },
    "INTC": {
        "Q2": "Turun 56.2% (9/16 thn, Med -1.7%): Efek klasik 'Sell in May' semikonduktor PC saat pesanan laptop konsumen melambat di musim panas.",
        "Q3": "Turun 62.5% (10/16 thn, Med -3.5%): Tekanan margin & revisi pesanan OEM PC menjelang akhir kuartal ketiga.",
    },
    "FCX": {
        "Q2": "Turun 56.2% (9/16 thn, Med -1.5%): Pelemahan permintaan tembaga fisik setelah puncak restocking musim semi Tiongkok.",
        "Q3": "Turun 62.5% (10/16 thn, Mean -4.2%, Med -6.3%): Perlambatan konstruksi musiman akhir musim panas & penguatan Dolar AS di Q3.",
    },
    "XOM": {
        "Q2": "Turun 56.2% (9/16 thn, Med -0.4%): Konsolidasi harga minyak mentah pertengahan tahun.",
        "Q3": "Turun 50.0% (Mean -0.9%, Med -0.8%): Penurunan margin kilang (crack spread) setelah puncak mengemudi musim panas berakhir.",
    },
    "MA": {
        "Q3": "Naik 81.2% (13/16 thn, Mean +6.0%, Med +5.2%): Puncak volume transaksi kartu lintas batas (cross-border summer travel) berbiaya tinggi.",
        "Q4": "Naik 93.8% (15/16 thn, Mean +9.0%, Med +8.1%): Rekor konsistensi tertinggi di Q4 berkat puncak belanja liburan Black Friday hingga Natal.",
    },
    "V": {"Q4": "Naik 81.2% (13/16 thn, Mean +9.7%, Med +12.3%): Lonjakan volume pembayaran ritel & e-commerce liburan akhir tahun."},
    "AMGN": {"Q3": "Naik 75.0% (12/16 thn, Med +8.7%): Konferensi medis musim gugur & rotasi defensif ke bioteknologi berarus kas kuat di bulan September."},
    "HD": {"Q3": "Naik 75.0% (12/16 thn, Med +5.6%): Penyelesaian proyek renovasi rumah musim panas & permintaan perbaikan pasca musim badai."},
    "COST": {"Q3": "Naik 75.0% (12/16 thn, Mean +5.1%): Belanja grosir Back-to-School & penimbunan barang rumah tangga menjelang musim gugur."},
    "AAL": {"Q3": "Turun 75.0% (12/16 thn, Mean -7.3%, Med -5.2%): Post-summer travel cliff; trafik penumpang anjlok di Agustus-September saat sekolah mulai."},
    "GE": {"Q3": "Turun 68.8% (11/16 thn, Mean -3.2%, Med -4.2%): De-risking institusional September pada saham industri dirgantara."},
    "BA": {"Q3": "Turun 56.2% (9/16 thn, Mean -1.9%, Med -5.4%): Penyesuaian jadwal pengiriman pesawat Q3 & tekanan rebalancing akhir kuartal."},
    "AMAT": {"Q3": "Turun 68.8% (11/16 thn, Mean -2.4%, Med -3.9%): Siklus pencernaan belanja modal wafer fab di kuartal ketiga."},
    "SMCI": {"Q3": "Turun 62.5% (10/16 thn, Med -4.1%): Jeda pengadaan server enterprise Eropa/AS selama liburan musim panas Juli-Agustus."},
    "DIS": {"Q3": "Turun 62.5% (10/16 thn, Mean -1.7%, Med -3.2%): Penurunan pengunjung taman hiburan di akhir Agustus/September saat tahun ajaran sekolah dimulai."},
    "DAL": {
        "Q3": "Turun 50.0% (Mean +0.5%, vs S&P -0.8%): Melambatnya perjalanan wisata setelah puncak Juli.",
        "Q4": "Naik 87.5% (14/16 thn, Mean +14.3%, Med +16.8%): Lonjakan pemesanan tiket liburan Thanksgiving/Natal & perjalanan korporasi akhir tahun.",
    },
    "BLK": {"Q4": "Naik 87.5% (14/16 thn, Mean +12.8%, Med +14.4%): Arus masuk ETF akhir tahun (year-end tax & portfolio reallocation) + performance fees Q4."},
    "FDX": {"Q4": "Naik 87.5% (14/16 thn, Mean +8.3%, Med +8.1%): Puncak volume pengiriman kargo & paket e-commerce musim liburan Oktober-Desember."},
    "DE": {"Q4": "Naik 87.5% (14/16 thn, Mean +10.0%): Tutup buku tahun fiskal 31 Oktober & pembukaan program pemesanan alat pertanian musim tanam berikutnya."},
    "AZO": {"Q4": "Naik 87.5% (14/16 thn, Mean +7.1%): Permintaan suku cadang perawatan mobil menghadapi cuaca dingin/salju akhir tahun."},
    "JPM": {"Q4": "Naik 81.2% (13/16 thn, Mean +12.0%, Med +12.0%): Reli perbankan akhir tahun, window dressing, & optimisme panduan NII/dividen tahun baru."},
    "BAC": {"Q4": "Naik 81.2% (13/16 thn, Mean +11.7%, Med +10.8%): Rotasi masuk institusi ke saham keuangan berkapitalisasi besar di kuartal keempat."},
    "NEM": {"Q4": "Turun 50.0% (Mean -0.6%, Med -2.0%): Pelepasan saham tambang emas saat investor beralih ke risk-on equity rally akhir tahun."},
}

# Short seasonal cue per symbol/quarter used to enrich per-year attribution
SHORT_SEASONAL_CUE: Dict[Tuple[str, int], str] = {
    ("AAPL", 1): "siklus pemangkasan pesanan komponen iPhone pasca-liburan",
    ("AAPL", 2): "momentum konferensi developer WWDC & ekosistem layanan",
    ("AAPL", 3): "siklus peluncuran iPhone baru September & Back-to-School",
    ("AAPL", 4): "kuartal pengiriman puncak liburan akhir tahun (Holiday Quarter)",
    ("MSFT", 2): "tutup buku tahun fiskal 30 Juni (enterprise quota flush Azure)",
    ("NVDA", 1): "pencairan CapEx data center awal tahun & konferensi GTC Maret",
    ("GOOGL", 1): "normalisasi musiman anggaran iklan digital Q1 pasca-liburan",
    ("AMZN", 2): "akumulasi menjelang Prime Day & ekspansi cloud AWS",
    ("META", 4): "evaluasi panduan belanja modal (CapEx) tahun berikutnya di earnings Oktober",
    ("AVGO", 4): "tutup buku tahun fiskal November, kenaikan dividen, & panduan jaringan/ASIC",
    ("ORCL", 3): "jeda kontrak lisensi musim panas (Q1 FY Oracle)",
    ("ORCL", 4): "pertengahan tahun fiskal Oracle (Q2 FY) yang secara historis lebih sepi",
    ("MA", 3): "puncak transaksi lintas batas perjalanan musim panas",
    ("MA", 4): "lonjakan transaksi belanja Black Friday hingga Natal",
    ("V", 4): "puncak volume pembayaran ritel & e-commerce liburan Q4",
    ("DAL", 4): "lonjakan tiket liburan Thanksgiving/Natal & perjalanan bisnis",
    ("AAL", 3): "anjloknya trafik wisata pasca-musim panas (post-summer travel cliff)",
    ("FDX", 4): "puncak volume pengiriman kargo e-commerce liburan",
    ("BLK", 4): "arus masuk ETF akhir tahun & biaya kinerja (performance fees) Q4",
    ("GLD", 1): "permintaan emas fisik awal tahun & lindung nilai inflasi",
    ("GLD", 4): "rotasi keluar dari safe-haven emas menuju aset berisiko akhir tahun",
    ("NEM", 4): "pelepasan saham tambang emas saat reli ekuitas akhir tahun",
    ("LRCX", 1): "pemesanan peralatan wafer fab awal tahun kalender",
    ("NFLX", 1): "rilis rekor tambahan pelanggan musim dingin Q4 di Januari",
    ("PGR", 1): "siklus pembaruan & repricing polis asuransi awal tahun",
    ("HAL", 3): "berakhirnya US summer driving season & koreksi jasa migas",
}


def _infer_reason(sym: str, qtr: int, row: Dict[str, Any], is_bull: bool) -> str:
    q_key = f"Q{qtr}"
    if sym in SPECIFIC_REASONS and q_key in SPECIFIC_REASONS[sym]:
        return SPECIFIC_REASONS[sym][q_key]

    sec = str(row.get("sector", ""))
    win = row.get("win_rate_pct", 50.0)
    loss = row.get("loss_rate_pct", 50.0)
    med = row.get("median_return_pct", 0.0)
    if is_bull:
        if qtr == 1:
            return f"Naik {win:.0f}% tahun (Med {med:+.1f}%): Alokasi anggaran awal tahun pada sektor {sec or 'utama'} & akumulasi institusional Q1."
        if qtr == 2:
            return f"Naik {win:.0f}% tahun (Med {med:+.1f}%): Akselerasi kontrak paruh pertama & momentum rilis kinerja musim semi ({sec or 'Core'})."
        if qtr == 3:
            return f"Naik {win:.0f}% tahun (Med {med:+.1f}%): Permintaan musiman paruh kedua & ketahanan arus kas terhadap volatilitas September."
        return f"Naik {win:.0f}% tahun (Med {med:+.1f}%): Dorongan belanja akhir tahun, window dressing institusi, & reli Q4 ({sec or 'Core'})."
    else:
        if qtr == 1:
            return f"Turun {loss:.0f}% tahun (Med {med:+.1f}%): Pencernaan permintaan pasca-liburan Q4 & rotasi portofolio awal tahun ({sec or 'Core'})."
        if qtr == 2:
            return f"Turun {loss:.0f}% tahun (Med {med:+.1f}%): Pelemahan musiman menjelang musim panas ('Sell in May' / rotasi sektor {sec or 'siklikal'})."
        if qtr == 3:
            return f"Turun {loss:.0f}% tahun (Med {med:+.1f}%): Tekanan 'September Effect', jeda aktivitas musim panas, & rebalancing kuartal ketiga."
        return f"Turun {loss:.0f}% tahun (Med {med:+.1f}%): Underperform terhadap reli Q4 akibat rotasi keluar dari {sec or 'sektor defensif'} atau siklus fiskal."


def _load_macro_quarterly() -> Dict[Tuple[int, int], Dict[str, Any]]:
    out: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if TREASURY_CSV.exists():
        ty = pd.read_csv(TREASURY_CSV)
        ty["date"] = pd.to_datetime(ty["date"])
        ty["year"] = ty["date"].dt.year
        ty["quarter"] = ty["date"].dt.quarter
        qty = (
            ty.dropna(subset=["yield_10y_tnx"])
            .groupby(["year", "quarter"])
            .agg(y10_end=("yield_10y_tnx", "last"))
            .reset_index()
        )
        qty["y10_chg_bps"] = (qty["y10_end"] - qty["y10_end"].shift(1)) * 100.0
        for _, r in qty.iterrows():
            key = (int(r["year"]), int(r["quarter"]))
            out.setdefault(key, {})["ust10y_pct"] = round(float(r["y10_end"]), 2)
            out[key]["ust10y_chg_bps"] = round(float(r["y10_chg_bps"]), 0) if pd.notna(r["y10_chg_bps"]) else 0.0

    if MACRO_CSV.exists():
        mc = pd.read_csv(MACRO_CSV)
        mc["Date"] = pd.to_datetime(mc["Date"])
        mc["year"] = mc["Date"].dt.year
        mc["quarter"] = mc["Date"].dt.quarter
        qmc = (
            mc.groupby(["year", "quarter"])
            .agg(
                cpi_yoy=("CPI_Headline_YoY_Pct", "last"),
                fed_funds=("FEDFUNDS", "last"),
                t10y2y=("T10Y2Y", "last"),
            )
            .reset_index()
        )
        # Forward-fill latest quarter if current month CPI/FedFunds is partial
        qmc[["cpi_yoy", "fed_funds", "t10y2y"]] = qmc[["cpi_yoy", "fed_funds", "t10y2y"]].ffill()
        for _, r in qmc.iterrows():
            key = (int(r["year"]), int(r["quarter"]))
            d = out.setdefault(key, {})
            if pd.notna(r["cpi_yoy"]):
                d["cpi_yoy_pct"] = round(float(r["cpi_yoy"]), 2)
            if pd.notna(r["fed_funds"]):
                d["fed_funds_pct"] = round(float(r["fed_funds"]), 2)
            if pd.notna(r["t10y2y"]):
                d["t10y2y_pct"] = round(float(r["t10y2y"]), 2)
    return out


def _build_stock_year_quarter_reason(
    sym: str,
    sec: str,
    yr: int,
    qtr: int,
    ret: float,
    sp_ret: float,
    sec_med: float,
    macro_info: Dict[str, Any],
) -> str:
    ev = YEAR_QUARTER_EVENTS.get(yr, {}).get(qtr, {})
    diff_sp = ret - sp_ret
    diff_sec = ret - sec_med
    cue = SHORT_SEASONAL_CUE.get((sym, qtr), "")
    y10 = macro_info.get("ust10y_pct")
    y10_bps = macro_info.get("ust10y_chg_bps")
    rate_tag = f" (10Y {y10:.2f}%, {y10_bps:+.0f} bps)" if y10 is not None and y10_bps is not None else ""

    if sym == "^GSPC":
        if ret >= 0:
            return f"Indeks S&P 500 naik {ret:+.2f}%{rate_tag}: {ev.get('bull', 'Didorong penguatan laba korporasi dan likuiditas pasar.')}"
        return f"Indeks S&P 500 terkoreksi {ret:+.2f}%{rate_tag}: {ev.get('bear', 'Tertekan pengetatan kondisi makro dan aksi jual institusi.')}"

    if ret >= 0:
        if sp_ret < -1.0:
            lead = f"Menguat {ret:+.1f}% melawan koreksi S&P 500 ({sp_ret:+.1f}%)"
        elif diff_sp >= 5.0:
            lead = f"Melonjak {ret:+.1f}% (outperform S&P {diff_sp:+.1f}%)"
        else:
            lead = f"Naik {ret:+.1f}% (S&P {sp_ret:+.1f}%)"

        sec_note = ""
        if sec and diff_sec >= 6.0:
            sec_note = f" Memimpin penguatan di atas median sektor {sec} ({sec_med:+.1f}%)."
        elif sec and sec_med >= 3.5:
            sec_note = f" Sejalan dengan arus masuk ke sektor {sec} (median {sec_med:+.1f}%)."

        cue_note = f" Katalis emiten: {cue}." if cue else ""
        macro_txt = ev.get("bull", "Didorong sentimen positif laba kuartalan dan akumulasi institusional.")
        return f"{lead}{rate_tag}: {macro_txt}{sec_note}{cue_note}"
    else:
        if sp_ret > 1.5:
            lead = f"Terkoreksi {ret:+.1f}% saat S&P 500 naik {sp_ret:+.1f}% (lag {diff_sp:+.1f}%)"
        elif diff_sp <= -5.0:
            lead = f"Turun tajam {ret:+.1f}% ({diff_sp:+.1f}% vs S&P)"
        else:
            lead = f"Melemah {ret:+.1f}% mengikuti koreksi S&P ({sp_ret:+.1f}%)"

        sec_note = ""
        if sec and diff_sec <= -6.0:
            sec_note = f" Tertekan faktor spesifik emiten dibanding median sektor {sec} ({sec_med:+.1f}%)."
        elif sec and sec_med <= -2.5:
            sec_note = f" Terbawa aksi jual luas pada sektor {sec} (median {sec_med:+.1f}%)."

        cue_note = f" Faktor musiman: {cue}." if cue else ""
        macro_txt = ev.get("bear", "Tertekan aksi ambil untung dan penyesuaian valuasi makro.")
        return f"{lead}{rate_tag}: {macro_txt}{sec_note}{cue_note}"


def main() -> None:
    macro_q = _load_macro_quarterly()

    with sqlite3.connect(str(DB_PATH)) as conn:
        tickers_df = pd.read_sql_query(
            "SELECT symbol, security_name, sector, industry FROM tickers", conn
        )
        meta_map = tickers_df.set_index("symbol").to_dict("index")

        placeholders = ",".join(["?"] * len(NOTABLE_UNIVERSE))
        df = pd.read_sql_query(
            f"""
            SELECT symbol, date, COALESCE(adj_close, close) AS px
            FROM daily_prices
            WHERE symbol IN ({placeholders})
              AND date >= '2010-01-01'
            ORDER BY symbol, date
            """,
            conn,
            params=NOTABLE_UNIVERSE,
        )

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter

    q_agg = (
        df.groupby(["symbol", "year", "quarter"])
        .agg(first_px=("px", "first"), last_px=("px", "last"), days=("px", "count"))
        .reset_index()
    )
    q_agg["prev_last_px"] = q_agg.groupby("symbol")["last_px"].shift(1)
    q_agg["q_ret_pct"] = np.where(
        q_agg["prev_last_px"].notna() & (q_agg["prev_last_px"] > 0),
        (q_agg["last_px"] / q_agg["prev_last_px"] - 1.0) * 100.0,
        (q_agg["last_px"] / q_agg["first_px"] - 1.0) * 100.0,
    )
    q_agg = q_agg[(q_agg["days"] >= 15) & (q_agg["year"] >= 2011)].copy()
    q_agg["sector"] = [meta_map.get(s, {}).get("sector", "") for s in q_agg["symbol"]]

    sp_q = q_agg[q_agg["symbol"] == "^GSPC"].set_index(["year", "quarter"])["q_ret_pct"].to_dict()
    q_agg["sp_ret_pct"] = [sp_q.get((y, q), 0.0) for y, q in zip(q_agg["year"], q_agg["quarter"])]
    q_agg["excess_ret_pct"] = q_agg["q_ret_pct"] - q_agg["sp_ret_pct"]

    sec_med_map = (
        q_agg[q_agg["symbol"] != "^GSPC"]
        .groupby(["year", "quarter", "sector"])["q_ret_pct"]
        .median()
        .to_dict()
    )

    summary = (
        q_agg.groupby(["symbol", "quarter"])
        .agg(
            n_years=("q_ret_pct", "count"),
            win_years=("q_ret_pct", lambda s: int(np.sum(s > 0))),
            loss_years=("q_ret_pct", lambda s: int(np.sum(s < 0))),
            win_rate_pct=("q_ret_pct", lambda s: round(float(np.mean(s > 0) * 100.0), 1)),
            loss_rate_pct=("q_ret_pct", lambda s: round(float(np.mean(s < 0) * 100.0), 1)),
            mean_return_pct=("q_ret_pct", lambda s: round(float(np.mean(s)), 2)),
            median_return_pct=("q_ret_pct", lambda s: round(float(np.median(s)), 2)),
            mean_excess_vs_sp500_pct=("excess_ret_pct", lambda s: round(float(np.mean(s)), 2)),
        )
        .reset_index()
    )

    valid_syms = set(summary.groupby("symbol")["n_years"].min()[lambda s: s >= 12].index)
    summary = summary[summary["symbol"].isin(valid_syms)].copy()
    q_agg = q_agg[q_agg["symbol"].isin(valid_syms)].copy()
    summary["security_name"] = [meta_map.get(s, {}).get("security_name", s) for s in summary["symbol"]]
    summary["sector"] = [meta_map.get(s, {}).get("sector", "") for s in summary["symbol"]]

    # Build yearly_regimes telemetry + macro reasons for all years 2011..2026 on exact valid_syms universe
    yearly_regimes: Dict[str, Any] = {}
    all_years = sorted(q_agg["year"].unique())
    for yr in all_years:
        yr_int = int(yr)
        yr_quarters: Dict[str, Any] = {}
        for qtr in [1, 2, 3, 4]:
            sub_yq = q_agg[(q_agg["year"] == yr_int) & (q_agg["quarter"] == qtr) & (q_agg["symbol"] != "^GSPC")]
            if sub_yq.empty:
                continue
            up_cnt = int((sub_yq["q_ret_pct"] > 0).sum())
            dn_cnt = int((sub_yq["q_ret_pct"] < 0).sum())
            tot_cnt = len(sub_yq)
            sec_rank = sub_yq.groupby("sector")["q_ret_pct"].median().sort_values(ascending=False)
            best_sec = str(sec_rank.index[0]) if len(sec_rank) > 0 and sec_rank.index[0] else "Technology"
            best_sec_med = round(float(sec_rank.iloc[0]), 2) if len(sec_rank) > 0 else 0.0
            worst_sec = str(sec_rank.index[-1]) if len(sec_rank) > 0 and sec_rank.index[-1] else "Energy"
            worst_sec_med = round(float(sec_rank.iloc[-1]), 2) if len(sec_rank) > 0 else 0.0

            ev = YEAR_QUARTER_EVENTS.get(yr_int, {}).get(qtr, {})
            m_info = macro_q.get((yr_int, qtr), {})
            yr_quarters[f"Q{qtr}"] = {
                "headline": ev.get("headline", f"Dinamika Makro Q{qtr} {yr_int}"),
                "bull_reason": ev.get("bull", ""),
                "bear_reason": ev.get("bear", ""),
                "sp500_ret_pct": round(float(sp_q.get((yr_int, qtr), 0.0)), 2),
                "ust10y_pct": m_info.get("ust10y_pct"),
                "ust10y_chg_bps": m_info.get("ust10y_chg_bps"),
                "cpi_yoy_pct": m_info.get("cpi_yoy_pct"),
                "fed_funds_pct": m_info.get("fed_funds_pct"),
                "up_stocks": up_cnt,
                "down_stocks": dn_cnt,
                "total_stocks": tot_cnt,
                "best_sector": best_sec,
                "best_sector_med_pct": best_sec_med,
                "worst_sector": worst_sec,
                "worst_sector_med_pct": worst_sec_med,
            }
        yearly_regimes[str(yr_int)] = yr_quarters

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_CSV, index=False)

    quarters_payload: Dict[str, Any] = {}
    for qtr in [1, 2, 3, 4]:
        q_sub = summary[(summary["quarter"] == qtr) & (summary["symbol"] != "^GSPC")].copy()
        q_sub["is_neg_med"] = q_sub["median_return_pct"] < 0
        bull_df = q_sub[q_sub["median_return_pct"] > 0].sort_values(
            ["win_rate_pct", "median_return_pct", "mean_return_pct"],
            ascending=[False, False, False],
        ).head(14)
        bear_df = q_sub.sort_values(
            ["is_neg_med", "loss_rate_pct", "median_return_pct", "mean_return_pct"],
            ascending=[False, False, True, True],
        ).head(14)
        bull_df = bull_df.drop(columns=["is_neg_med"])
        bear_df = bear_df.drop(columns=["is_neg_med"])

        bull_records = []
        for r in bull_df.to_dict("records"):
            r["reason"] = _infer_reason(r["symbol"], qtr, r, is_bull=True)
            bull_records.append(r)

        bear_records = []
        for r in bear_df.to_dict("records"):
            r["reason"] = _infer_reason(r["symbol"], qtr, r, is_bull=False)
            bear_records.append(r)

        sp_row = summary[(summary["quarter"] == qtr) & (summary["symbol"] == "^GSPC")].to_dict("records")
        quarters_payload[f"Q{qtr}"] = {
            "theme": QUARTER_THEMES[f"Q{qtr}"],
            "sp500_benchmark": sp_row[0] if sp_row else {},
            "top_bullish": bull_records,
            "top_bearish": bear_records,
        }

    priority_order = FLAGSHIP_11 + [
        "MA", "V", "NFLX", "LRCX", "TSM", "DAL", "AAL", "FDX", "BLK", "JPM", "BAC", "GS",
        "GLD", "NEM", "CAH", "NKE", "KR", "COST", "HD", "HAL", "FCX", "XOM", "GE", "BA", "AMAT", "INTC", "PGR", "LMT", "RTX", "DE"
    ]
    ordered_syms = [s for s in priority_order if s in valid_syms] + [
        s for s in sorted(valid_syms) if s not in priority_order
    ]

    stock_profiles: Dict[str, Any] = {}
    heatmap_rows: List[Dict[str, Any]] = []

    for sym in ordered_syms:
        rows = summary[summary["symbol"] == sym].sort_values("quarter").to_dict("records")
        if len(rows) < 4:
            continue
        sec_str = str(meta_map.get(sym, {}).get("sector", ""))
        q_map: Dict[str, Any] = {}
        best_q = max(rows, key=lambda x: (x["win_rate_pct"], x["median_return_pct"]))
        worst_q = min(rows, key=lambda x: (x["median_return_pct"], -x["loss_rate_pct"]))

        for r in rows:
            q_num = int(r["quarter"])
            q_key = f"Q{q_num}"
            is_b = r["median_return_pct"] >= 0 and r["win_rate_pct"] >= 55.0
            q_map[q_key] = {
                "win_rate_pct": r["win_rate_pct"],
                "loss_rate_pct": r["loss_rate_pct"],
                "win_years": r["win_years"],
                "loss_years": r["loss_years"],
                "n_years": r["n_years"],
                "mean_return_pct": r["mean_return_pct"],
                "median_return_pct": r["median_return_pct"],
                "excess_vs_sp500_pct": r["mean_excess_vs_sp500_pct"],
                "reason": _infer_reason(sym, q_num, r, is_bull=is_b),
                "bull_reason": _infer_reason(sym, q_num, r, is_bull=True),
                "bear_reason": _infer_reason(sym, q_num, r, is_bull=False),
            }

        sym_q = q_agg[q_agg["symbol"] == sym]
        piv = sym_q.pivot(index="year", columns="quarter", values="q_ret_pct").sort_index()
        yearly_list = []
        for yr, yrow in piv.iterrows():
            yr_int = int(yr)
            q_reasons: Dict[str, str] = {}
            q_vals: Dict[str, Any] = {}
            for q_num in [1, 2, 3, 4]:
                qk = f"Q{q_num}"
                raw_v = yrow.get(q_num)
                if pd.notna(raw_v):
                    v_float = round(float(raw_v), 2)
                    q_vals[qk] = v_float
                    sp_v = float(sp_q.get((yr_int, q_num), 0.0))
                    s_med = float(sec_med_map.get((yr_int, q_num, sec_str), sp_v))
                    m_inf = macro_q.get((yr_int, q_num), {})
                    q_reasons[qk] = _build_stock_year_quarter_reason(
                        sym, sec_str, yr_int, q_num, v_float, sp_v, s_med, m_inf
                    )
                else:
                    q_vals[qk] = None

            yearly_list.append(
                {
                    "year": yr_int,
                    "Q1": q_vals["Q1"],
                    "Q2": q_vals["Q2"],
                    "Q3": q_vals["Q3"],
                    "Q4": q_vals["Q4"],
                    "reasons": q_reasons,
                }
            )

        best_q_key = f"Q{int(best_q['quarter'])}"
        worst_q_key = f"Q{int(worst_q['quarter'])}"
        profile = {
            "symbol": sym,
            "security_name": meta_map.get(sym, {}).get("security_name", sym),
            "sector": sec_str,
            "best_quarter": best_q_key,
            "worst_quarter": worst_q_key,
            "quarters": q_map,
            "yearly_history": yearly_list,
        }
        stock_profiles[sym] = profile

        if sym != "^GSPC":
            heatmap_rows.append(profile)

    payload = {
        "available": True,
        "sample_window": "2011-2026 (16 Years · us_equities.db + FRED Macro & Treasury)",
        "universe_analyzed": len(stock_profiles),
        "yearly_regimes": yearly_regimes,
        "quarters": quarters_payload,
        "heatmap_rows": heatmap_rows,
        "stock_profiles": stock_profiles,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"[OK] Saved enriched 4-quarter seasonality + per-year reasons JSON "
        f"({len(stock_profiles)} profiles, {len(yearly_regimes)} yearly regimes) -> {OUT_JSON.name}"
    )


if __name__ == "__main__":
    main()
