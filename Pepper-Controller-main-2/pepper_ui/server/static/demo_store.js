/* demo_store.js - Pepper UI Local Demo Store
 * Uses localStorage to persist users, appointments, doctors, schedules, emergencies.
 * window.STORE is the global API used by all pages.
 */
(function () {
  'use strict';

  var K = {
    USERS:        'pepper_users',
    SESSION:      'pepper_session',
    APPOINTMENTS: 'pepper_appointments',
    DOCTORS:      'pepper_doctors',
    SCHEDULES:    'pepper_schedules',
    EMERGENCIES:  'pepper_emergencies',
    TRIAGES:      'pepper_triages'
  };

  function load(key) {
    try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; }
  }

  function save(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  }

  function getUsers()    { return load(K.USERS)   || []; }
  function saveUsers(u)  { save(K.USERS, u); }

  var SEED_VERSION = 'v3';

  /* ---- Seed default data on first run or version change ---- */
  (function seedDefaults() {
    if (!load(K.USERS) || load('pepper_seed_ver') !== SEED_VERSION) {
      save('pepper_seed_ver', SEED_VERSION);
      save(K.USERS, [
        /* ============ PATIENTS (password: 123 for all) ============ */
        { id: '100', name: 'Ahmed Ali',         role: 'patient', password: '123', case_number: 'CASE-001',
          age: 52, gender: 'Male', blood_type: 'A+',
          medical_history: 'Hypertension (10 yrs), Type 2 Diabetes (5 yrs), mild left-ventricular hypertrophy',
          allergies: 'Penicillin',
          current_medications: 'Amlodipine 5mg daily, Metformin 500mg twice daily, Aspirin 81mg daily',
          notes: 'BP well-controlled on current regimen. Last HbA1c 7.2%. Due for echo follow-up.' },
        { id: '101', name: 'Sara Hassan',        role: 'patient', password: '123', case_number: 'CASE-002',
          age: 34, gender: 'Female', blood_type: 'O+',
          medical_history: 'Asthma since childhood, seasonal allergic rhinitis',
          allergies: 'Sulfa drugs, dust mites',
          current_medications: 'Salbutamol inhaler PRN, Fluticasone nasal spray daily',
          notes: 'Asthma well-controlled. Uses inhaler 1-2x/week. Avoid NSAIDs.' },
        { id: '102', name: 'Mohamed Ibrahim',    role: 'patient', password: '123', case_number: 'CASE-003',
          age: 67, gender: 'Male', blood_type: 'B+',
          medical_history: 'Coronary artery disease (stent placed 2023), atrial fibrillation, hyperlipidemia',
          allergies: 'None known',
          current_medications: 'Warfarin 5mg daily, Atorvastatin 40mg daily, Bisoprolol 2.5mg daily',
          notes: 'INR target 2.0-3.0. High fall risk. Requires anticoagulation monitoring.' },
        { id: '103', name: 'Fatma Khaled',       role: 'patient', password: '123', case_number: 'CASE-004',
          age: 28, gender: 'Female', blood_type: 'AB+',
          medical_history: 'Gestational diabetes (current pregnancy, 28 weeks), iron-deficiency anemia',
          allergies: 'Codeine (nausea)',
          current_medications: 'Insulin Glargine 10 units nightly, Ferrous sulfate 325mg daily, Prenatal vitamins',
          notes: 'High-risk pregnancy. Weekly glucose monitoring. Delivery planned at 38 weeks.' },
        { id: '104', name: 'Omar Nabil',         role: 'patient', password: '123', case_number: 'CASE-005',
          age: 45, gender: 'Male', blood_type: 'O-',
          medical_history: 'Chronic lower back pain (L4-L5 disc herniation), mild depression',
          allergies: 'Ibuprofen (GI bleeding)',
          current_medications: 'Pregabalin 75mg twice daily, Paracetamol 1g PRN, Sertraline 50mg daily',
          notes: 'MRI 2024 shows stable disc herniation. PT referral active. Avoid heavy lifting.' },
        { id: '105', name: 'Nadia Salem',        role: 'patient', password: '123', case_number: 'CASE-006',
          age: 55, gender: 'Female', blood_type: 'A-',
          medical_history: 'Rheumatoid arthritis (15 yrs), osteoporosis, hypothyroidism',
          allergies: 'Methotrexate (liver toxicity)',
          current_medications: 'Hydroxychloroquine 200mg twice daily, Levothyroxine 75mcg daily, Calcium/Vitamin D, Alendronate 70mg weekly',
          notes: 'DXA scan due in 6 months. Thyroid levels stable. Joint deformity in hands.' },
        { id: '106', name: 'Karim Farouk',       role: 'patient', password: '123', case_number: 'CASE-007',
          age: 19, gender: 'Male', blood_type: 'B-',
          medical_history: 'Type 1 Diabetes since age 8, celiac disease',
          allergies: 'Gluten (celiac), latex',
          current_medications: 'Insulin Aspart (mealtime), Insulin Glargine (basal), Gluten-free diet',
          notes: 'Uses insulin pump. Last HbA1c 6.8%. Strict gluten-free diet required.' },
        { id: '107', name: 'Heba Mahmoud',       role: 'patient', password: '123', case_number: 'CASE-008',
          age: 41, gender: 'Female', blood_type: 'O+',
          medical_history: 'Migraine with aura (chronic), anxiety disorder',
          allergies: 'Ergotamine, strong perfumes (trigger)',
          current_medications: 'Topiramate 50mg daily, Sumatriptan 50mg PRN, Escitalopram 10mg daily',
          notes: 'Migraine diary: 3-4 episodes/month. Avoid triggers: stress, lack of sleep, bright lights.' },
        { id: '108', name: 'Youssef Adel',       role: 'patient', password: '123', case_number: 'CASE-009',
          age: 72, gender: 'Male', blood_type: 'A+',
          medical_history: 'COPD (former smoker, 30 pack-years), benign prostatic hyperplasia, hearing loss',
          allergies: 'ACE inhibitors (cough)',
          current_medications: 'Tiotropium inhaler daily, Salbutamol PRN, Tamsulosin 0.4mg daily',
          notes: 'FEV1 55% predicted. Pulmonary rehab recommended. Annual flu vaccine.' },
        { id: '109', name: 'Mariam Tarek',       role: 'patient', password: '123', case_number: 'CASE-010',
          age: 8, gender: 'Female', blood_type: 'O+',
          medical_history: 'Epilepsy (absence seizures, diagnosed age 5), mild learning disability',
          allergies: 'None known',
          current_medications: 'Sodium Valproate 200mg twice daily',
          notes: 'Seizure-free for 14 months. EEG follow-up scheduled. School support plan in place.' },
        { id: '110', name: 'Hassan Mostafa',     role: 'patient', password: '123', case_number: 'CASE-011',
          age: 60, gender: 'Male', blood_type: 'AB-',
          medical_history: 'Chronic kidney disease stage 3, gout, hypertension',
          allergies: 'Allopurinol (severe rash)',
          current_medications: 'Losartan 50mg daily, Febuxostat 40mg daily, Sodium bicarbonate 500mg twice daily',
          notes: 'eGFR 42. Avoid nephrotoxic drugs. Low-protein diet. Nephrology every 3 months.' },
        { id: '111', name: 'Aya Mohamed',        role: 'patient', password: '123', case_number: 'CASE-012',
          age: 25, gender: 'Female', blood_type: 'B+',
          medical_history: 'Polycystic ovary syndrome (PCOS), insulin resistance, acne',
          allergies: 'None known',
          current_medications: 'Combined oral contraceptive pill, Metformin 500mg daily, Topical retinoid',
          notes: 'BMI 31. Weight management plan. Hormonal profile being monitored.' },
        { id: '112', name: 'Amr Sherif',         role: 'patient', password: '123', case_number: 'CASE-013',
          age: 38, gender: 'Male', blood_type: 'A+',
          medical_history: 'Peptic ulcer disease (H. pylori treated), GERD, anxiety',
          allergies: 'Aspirin (gastric), NSAIDs',
          current_medications: 'Omeprazole 20mg daily, Buspirone 10mg twice daily',
          notes: 'H. pylori eradicated. Endoscopy clear 2024. Avoid spicy food and late meals.' },
        { id: '113', name: 'Dina Wael',          role: 'patient', password: '123', case_number: 'CASE-014',
          age: 47, gender: 'Female', blood_type: 'O-',
          medical_history: 'Breast cancer (stage II, mastectomy 2023), lymphedema',
          allergies: 'Tamoxifen (blood clots risk noted)',
          current_medications: 'Anastrozole 1mg daily, Compression sleeve, Calcium/Vitamin D',
          notes: 'In remission. Oncology follow-up every 6 months. Mammogram due.' },
        { id: '114', name: 'Khaled Hossam',      role: 'patient', password: '123', case_number: 'CASE-015',
          age: 31, gender: 'Male', blood_type: 'B+',
          medical_history: "Crohn's disease (ileocolonic), vitamin B12 deficiency",
          allergies: 'Mesalamine (headache)',
          current_medications: 'Azathioprine 150mg daily, B12 injections monthly, Folic acid 5mg daily',
          notes: 'Mild inflammation on colonoscopy. Biologic therapy may be needed. Low-residue diet.' },
        { id: '115', name: 'Noura Bassem',       role: 'patient', password: '123', case_number: 'CASE-016',
          age: 63, gender: 'Female', blood_type: 'A+',
          medical_history: 'Osteoarthritis (bilateral knees), hypertension, obesity (BMI 38)',
          allergies: 'Codeine (constipation)',
          current_medications: 'Amlodipine 10mg daily, Paracetamol 1g TDS, Glucosamine supplement',
          notes: 'Knee replacement candidate. Weight loss program initiated. Physiotherapy 2x/week.' },
        { id: '116', name: 'Tamer Essam',        role: 'patient', password: '123', case_number: 'CASE-017',
          age: 50, gender: 'Male', blood_type: 'O+',
          medical_history: 'Hepatitis C (treated, SVR 2022), liver fibrosis F2, fatty liver',
          allergies: 'None known',
          current_medications: 'Ursodeoxycholic acid 250mg twice daily, Low-fat diet',
          notes: 'SVR confirmed. FibroScan every 12 months. Liver enzymes stable. No alcohol.' },
        { id: '117', name: 'Rania Gamal',        role: 'patient', password: '123', case_number: 'CASE-018',
          age: 36, gender: 'Female', blood_type: 'AB+',
          medical_history: 'Systemic lupus erythematosus (SLE), lupus nephritis class III',
          allergies: 'Trimethoprim (rash)',
          current_medications: 'Mycophenolate 500mg BD, Hydroxychloroquine 200mg daily, Prednisolone 5mg daily',
          notes: 'Renal function stable. Avoid sun exposure. Immunosuppressed - avoid live vaccines.' },
        { id: '118', name: 'Sherif Walid',       role: 'patient', password: '123', case_number: 'CASE-019',
          age: 58, gender: 'Male', blood_type: 'A-',
          medical_history: "Parkinson's disease (diagnosed 2021), mild cognitive impairment, orthostatic hypotension",
          allergies: 'Metoclopramide (worsens tremor)',
          current_medications: 'Levodopa/Carbidopa 100/25 TDS, Rivastigmine patch 4.6mg',
          notes: 'Tremor-dominant PD. Fall risk. Occupational therapy referral. Swallow assessment needed.' },
        { id: '119', name: 'Layla Samir',        role: 'patient', password: '123', case_number: 'CASE-020',
          age: 22, gender: 'Female', blood_type: 'O+',
          medical_history: 'Iron-deficiency anemia (chronic heavy periods), vitamin D deficiency',
          allergies: 'None known',
          current_medications: 'Ferrous fumarate 210mg BD, Vitamin D3 50000 IU weekly, Tranexamic acid',
          notes: 'Hb improving (last 10.2). Gynecology referral for menorrhagia workup.' },
        { id: '120', name: 'Alaa Ramadan',       role: 'patient', password: '123', case_number: 'CASE-021',
          age: 44, gender: 'Male', blood_type: 'B-',
          medical_history: 'Obstructive sleep apnea (severe, AHI 42), obesity (BMI 40), hypertension',
          allergies: 'None known',
          current_medications: 'CPAP machine nightly, Lisinopril 20mg daily',
          notes: 'CPAP compliance 65%. Weight loss surgery consultation pending.' },
        { id: '121', name: 'Mona Sayed',         role: 'patient', password: '123', case_number: 'CASE-022',
          age: 70, gender: 'Female', blood_type: 'A+',
          medical_history: 'Heart failure (HFrEF, EF 35%), atrial fibrillation, Type 2 Diabetes',
          allergies: 'Digoxin (toxicity history)',
          current_medications: 'Sacubitril/Valsartan 50mg BD, Dapagliflozin 10mg, Furosemide 40mg, Apixaban 5mg BD',
          notes: 'Fluid restriction 1.5L/day. Daily weight monitoring. NYHA class II.' },
        { id: '122', name: 'George Hany',        role: 'patient', password: '123', case_number: 'CASE-023',
          age: 33, gender: 'Male', blood_type: 'O+',
          medical_history: 'Multiple sclerosis (relapsing-remitting, diagnosed 2020), optic neuritis (resolved)',
          allergies: 'None known',
          current_medications: 'Dimethyl fumarate 240mg BD, Vitamin D 2000 IU daily',
          notes: 'MRI shows stable lesion load. No relapses in 18 months. Annual neuro review due.' },
        { id: '123', name: 'Yasmin Ashraf',      role: 'patient', password: '123', case_number: 'CASE-024',
          age: 29, gender: 'Female', blood_type: 'B+',
          medical_history: "Hashimoto's thyroiditis, depression, irritable bowel syndrome (IBS-D)",
          allergies: 'Lactose intolerant',
          current_medications: 'Levothyroxine 100mcg daily, Fluoxetine 20mg daily, Loperamide PRN',
          notes: 'TSH stable. Low-FODMAP diet trial. Mental health stable.' },
        { id: '124', name: 'Samy Lotfy',         role: 'patient', password: '123', case_number: 'CASE-025',
          age: 75, gender: 'Male', blood_type: 'AB+',
          medical_history: "Alzheimer's disease (moderate stage), prostate cancer (Gleason 6, watchful waiting), cataracts",
          allergies: 'Ciprofloxacin (tendon pain)',
          current_medications: 'Donepezil 10mg daily, Memantine 10mg daily, Eye drops (Timolol)',
          notes: 'Cognitive decline progressive. Caregiver support needed. Cataract surgery planned.' },
        { id: '125', name: 'Hala Nasser',        role: 'patient', password: '123', case_number: 'CASE-026',
          age: 42, gender: 'Female', blood_type: 'O-',
          medical_history: "Graves' disease (hyperthyroidism), anxiety, palpitations",
          allergies: 'Propylthiouracil (liver toxicity)',
          current_medications: 'Carbimazole 15mg daily, Propranolol 40mg BD',
          notes: 'Thyroid levels improving. Radioactive iodine therapy under consideration.' },
        { id: '126', name: 'Tarek Samy',         role: 'patient', password: '123', case_number: 'CASE-027',
          age: 56, gender: 'Male', blood_type: 'A+',
          medical_history: 'Peripheral artery disease, Type 2 Diabetes, ex-smoker (quit 2020)',
          allergies: 'Contrast dye (mild reaction)',
          current_medications: 'Cilostazol 100mg BD, Metformin 1000mg BD, Rosuvastatin 20mg, Aspirin 81mg',
          notes: 'Claudication improving with exercise. ABI 0.7. Vascular surgery consult if worsens.' },
        { id: '127', name: 'Iman Rashid',        role: 'patient', password: '123', case_number: 'CASE-028',
          age: 48, gender: 'Female', blood_type: 'B-',
          medical_history: 'Fibromyalgia, chronic fatigue syndrome, TMJ disorder',
          allergies: 'Gabapentin (dizziness)',
          current_medications: 'Duloxetine 60mg daily, Amitriptyline 10mg at night, Physiotherapy',
          notes: 'Pain score averaging 5/10. Sleep study normal. Multidisciplinary pain clinic referral.' },
        { id: '128', name: 'Wael Ibrahim',       role: 'patient', password: '123', case_number: 'CASE-029',
          age: 65, gender: 'Male', blood_type: 'O+',
          medical_history: 'Recurrent kidney stones (calcium oxalate), gout, mild CKD stage 2',
          allergies: 'None known',
          current_medications: 'Potassium citrate 10mEq BD, Allopurinol 100mg daily, High fluid intake 3L/day',
          notes: 'Last stone passed 6 months ago. CT KUB clear. Low-oxalate diet counseling done.' },
        { id: '129', name: 'Salma Fathy',        role: 'patient', password: '123', case_number: 'CASE-030',
          age: 16, gender: 'Female', blood_type: 'A-',
          medical_history: 'Scoliosis (thoracolumbar, 28-degree curve), exercise-induced asthma',
          allergies: 'None known',
          current_medications: 'Salbutamol inhaler PRN (before exercise), Back brace (nighttime)',
          notes: 'Curve stable on X-ray. Physiotherapy 3x/week. Surgical review if >35 degrees.' },
        /* ============ STAFF (password: 123 for all) ============ */
        { id: '200', name: 'Staff Supervisor',   role: 'staff',   password: '123' },
        { id: '201', name: 'Nurse Mona Saad',    role: 'staff',   password: '123' },
        { id: '202', name: 'Nurse Ahmed Hamdy',  role: 'staff',   password: '123' },
        { id: '203', name: 'Receptionist Sara',  role: 'staff',   password: '123' },
        { id: '204', name: 'Admin Tarek Nour',   role: 'staff',   password: '123' }
      ]);
    }

    if (!load(K.DOCTORS)) {
      save(K.DOCTORS, [
        { id: 'd01', name: 'Dr. Ahmed Salem',         department: 'Cardiology',              room: 'Room 101, First Floor'    },
        { id: 'd02', name: 'Dr. Mona Khaled',          department: 'Cardiology',              room: 'Room 102, First Floor'    },
        { id: 'd03', name: 'Dr. Mohamed Fathy',        department: 'Cardiology',              room: 'Room 103, First Floor'    },
        { id: 'd04', name: 'Dr. Ahmed Yehia',          department: 'Cardiology',              room: 'Room 104, First Floor'    },
        { id: 'd05', name: 'Dr. Abdallah Ahmed',       department: 'Cardiology',              room: 'Room 106, First Floor'    },
        { id: 'd06', name: 'Dr. Abdelrahman Salem',    department: 'Cardiology',              room: 'Room 105, First Floor'    },
        { id: 'd07', name: 'Dr. Youssef Nabil',        department: 'Orthopedics',             room: 'Room 210, Second Floor'   },
        { id: 'd08', name: 'Dr. Ehab Orfy',            department: 'Orthopedics',             room: 'Room 211, Second Floor'   },
        { id: 'd09', name: 'Dr. Walid Fayez Fahmy',    department: 'Orthopedics',             room: 'Room 212, Second Floor'   },
        { id: 'd10', name: 'Dr. Omar El-Sabiaay',      department: 'Orthopedics',             room: 'Room 213, Second Floor'   },
        { id: 'd11', name: 'Dr. Layla Ibrahim',        department: 'Neurology',               room: 'Room 305, Third Floor'    },
        { id: 'd12', name: 'Dr. Ahmed Mohamed',        department: 'Neurology',               room: 'Room 306, Third Floor'    },
        { id: 'd13', name: 'Dr. Mohamed Hamdy',        department: 'Neurology',               room: 'Room 307, Third Floor'    },
        { id: 'd14', name: 'Dr. Mohamed Ali',          department: 'Neurology',               room: 'Room 308, Third Floor'    },
        { id: 'd15', name: 'Dr. Omar Farouk',          department: 'Internal Medicine',       room: 'Room 120, First Floor'    },
        { id: 'd16', name: 'Dr. Asmaa Elsayed',        department: 'Internal Medicine',       room: 'Room 121, First Floor'    },
        { id: 'd17', name: 'Dr. Hisham Mohamed',       department: 'Internal Medicine',       room: 'Room 122, First Floor'    },
        { id: 'd18', name: 'Dr. Hana Samir',           department: 'Pediatrics',              room: 'Room 215, Second Floor'   },
        { id: 'd19', name: 'Dr. Amany Yahya',          department: 'Pediatrics',              room: 'Room 216, Second Floor'   },
        { id: 'd20', name: 'Dr. Amira Ramadan',        department: 'Pediatrics',              room: 'Room 217, Second Floor'   },
        { id: 'd21', name: 'Dr. Doaa Hebaa',           department: 'Pediatrics',              room: 'Room 218, Second Floor'   },
        { id: 'd22', name: 'Dr. Karim Adel',           department: 'ENT',                     room: 'Room 310, Third Floor'    },
        { id: 'd23', name: 'Dr. Rania Ghazy',          department: 'ENT',                     room: 'Room 311, Third Floor'    },
        { id: 'd24', name: 'Dr. Amr Adel',             department: 'ENT',                     room: 'Room 312, Third Floor'    },
        { id: 'd25', name: 'Dr. Islam Fathy',          department: 'ENT',                     room: 'Room 313, Third Floor'    },
        { id: 'd26', name: 'Dr. Nadia Sami',           department: 'Radiology',               room: 'Room 050, Ground Floor'   },
        { id: 'd27', name: 'Dr. Radiology Specialist', department: 'Radiology',               room: 'Room 051, Ground Floor'   },
        { id: 'd28', name: 'Dr. Islam Mohamed',        department: 'Dermatology',             room: 'Room 130, First Floor'    },
        { id: 'd29', name: 'Dr. Gamal Murad',          department: 'Dermatology',             room: 'Room 131, First Floor'    },
        { id: 'd30', name: 'Dr. Mai Kamal',            department: 'Dermatology',             room: 'Room 132, First Floor'    },
        { id: 'd31', name: 'Dr. Maha Marwan',          department: 'Dermatology',             room: 'Room 133, First Floor'    },
        { id: 'd32', name: 'Dr. Yasmin Maamoun',       department: 'Dermatology',             room: 'Room 134, First Floor'    },
        { id: 'd33', name: 'Dr. Mohamed Kabary',       department: 'Dermatology',             room: 'Room 135, First Floor'    },
        { id: 'd34', name: 'Dr. Mohamed Adly',         department: 'Ophthalmology',           room: 'Room 140, First Floor'    },
        { id: 'd35', name: 'Dr. Makary Rasmy',         department: 'Ophthalmology',           room: 'Room 141, First Floor'    },
        { id: 'd36', name: 'Dr. Ehab Ali',             department: 'Dentistry',               room: 'Room 060, Ground Floor'   },
        { id: 'd37', name: 'Dr. Darine Mamdouh',       department: 'Dentistry',               room: 'Room 061, Ground Floor'   },
        { id: 'd38', name: 'Dr. Heba Ibrahim',         department: 'Dentistry',               room: 'Room 062, Ground Floor'   },
        { id: 'd39', name: 'Dr. Sherif Moustafa',      department: 'Dentistry',               room: 'Room 063, Ground Floor'   },
        { id: 'd40', name: 'Dr. Mai Salah Helal',      department: 'Dentistry',               room: 'Room 064, Ground Floor'   },
        { id: 'd41', name: 'Dr. Aly Yahia',            department: 'Dentistry',               room: 'Room 065, Ground Floor'   },
        { id: 'd42', name: 'Dr. Omar Abdelkhalek',     department: 'Pulmonology',             room: 'Room 220, Second Floor'   },
        { id: 'd43', name: 'Dr. Abdelhamid Hassan',    department: 'Pulmonology',             room: 'Room 221, Second Floor'   },
        { id: 'd44', name: 'Dr. Abdelhamid Saber',     department: 'Pulmonology',             room: 'Room 222, Second Floor'   },
        { id: 'd45', name: 'Dr. Karim Abdelsalam',     department: 'Obstetrics & Gynecology', room: 'Room 230, Second Floor'   },
        { id: 'd46', name: 'Dr. Ahmed El-Erian',       department: 'Obstetrics & Gynecology', room: 'Room 231, Second Floor'   },
        { id: 'd47', name: 'Dr. Sabah Ghareeb',        department: 'Obstetrics & Gynecology', room: 'Room 232, Second Floor'   },
        { id: 'd48', name: 'Dr. Mohamed Ahmed',        department: 'Nephrology',              room: 'Room 320, Third Floor'    },
        { id: 'd49', name: 'Dr. Ziad Abdelaziz',       department: 'Clinical Oncology',       room: 'Room 410, Fourth Floor'   },
        { id: 'd50', name: 'Dr. Hany William Zakaria',  department: 'Clinical Oncology',      room: 'Room 411, Fourth Floor'   },
        { id: 'd51', name: 'Dr. Mohamed Essam',        department: 'Clinical Oncology',       room: 'Room 412, Fourth Floor'   },
        { id: 'd52', name: 'Dr. Mohamed Raafat',       department: 'Neurosurgery',            room: 'Room 420, Fourth Floor'   },
        { id: 'd53', name: 'Dr. Ahmed Ismael',         department: 'Neurosurgery',            room: 'Room 421, Fourth Floor'   },
        { id: 'd54', name: 'Dr. Bassem Abdelrahman',   department: 'Vascular Surgery',        room: 'Room 240, Second Floor'   },
        { id: 'd55', name: 'Dr. Sherif Moamen',        department: 'Vascular Surgery',        room: 'Room 241, Second Floor'   },
        { id: 'd56', name: 'Dr. Mohamed Ragab',        department: 'Vascular Surgery',        room: 'Room 242, Second Floor'   },
        { id: 'd57', name: 'Dr. Tamer Ahmad ElSayed',  department: 'Physiotherapy',           room: 'Room 070, Ground Floor'   },
        { id: 'd58', name: 'Dr. Islam Abdelkader',     department: 'Physiotherapy',           room: 'Room 071, Ground Floor'   },
        { id: 'd59', name: 'Dr. Mohamed Ehab',         department: 'Physiotherapy',           room: 'Room 072, Ground Floor'   },
        { id: 'd60', name: 'Dr. Ahmed Fouad',          department: 'Plastic Surgery',         room: 'Room 430, Fourth Floor'   },
        { id: 'd61', name: 'Dr. Yasmine Adel',         department: 'Hepatology',              room: 'Room 330, Third Floor'    },
        { id: 'd62', name: 'Dr. Azza Ismail',          department: 'Oral Surgery',            room: 'Room 067, Ground Floor'   },
        { id: 'd63', name: 'Dr. Nadine ElBanby',       department: 'Audiology',               room: 'Room 150, First Floor'    },
        { id: 'd64', name: 'Dr. Diaa ElRahman',        department: 'Audiology',               room: 'Room 151, First Floor'    },
        { id: 'd65', name: 'Dr. Sameh Mansour',        department: 'Gastroenterology',        room: 'Room 250, Second Floor'   },
        { id: 'd66', name: 'Dr. Hana Gaber',           department: 'Gastroenterology',        room: 'Room 251, Second Floor'   },
        { id: 'd67', name: 'Dr. Sara Hassan',          department: 'Endocrinology',           room: 'Room 340, Third Floor'    },
        { id: 'd68', name: 'Dr. Nadia Fahmy',          department: 'Endocrinology',           room: 'Room 341, Third Floor'    },
        { id: 'd69', name: 'Dr. Walaa Sabry',          department: 'Psychiatry',              room: 'Room 440, Fourth Floor'   },
        { id: 'd70', name: 'Dr. Maha Nabil',           department: 'Psychiatry',              room: 'Room 441, Fourth Floor'   },
        { id: 'd71', name: 'Dr. Kerollos Wadie',       department: 'Emergency Medicine',      room: 'Emergency - Ground Floor' },
        { id: 'd72', name: 'Dr. Ramy Khalil',          department: 'Emergency Medicine',      room: 'Emergency - Ground Floor' },
        { id: 'd73', name: 'Dr. Tarek Samy',           department: 'Urology',                 room: 'Room 260, Second Floor'   },
        { id: 'd74', name: 'Dr. Wael Ibrahim',         department: 'Urology',                 room: 'Room 261, Second Floor'   },
        { id: 'd75', name: 'Dr. Khaled Salama',        department: 'General Surgery',         room: 'Room 270, Second Floor'   },
        { id: 'd76', name: 'Dr. Osama Lotfy',          department: 'General Surgery',         room: 'Room 271, Second Floor'   },
        { id: 'd77', name: 'Dr. Iman Rashid',          department: 'Rheumatology',            room: 'Room 350, Third Floor'    },
        { id: 'd78', name: 'Dr. Fatma Morsy',          department: 'Hematology',              room: 'Room 360, Third Floor'    },
        { id: 'd79', name: 'Dr. Noura Tawfik',         department: 'Clinical Nutrition',      room: 'Room 160, First Floor'    },
        { id: 'd80', name: 'Dr. Hossam Barakat',       department: 'Sleep Medicine',          room: 'Room 450, Fourth Floor'   }
      ]);
    }

    if (!load(K.SCHEDULES)) {
      save(K.SCHEDULES, {
        d01: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Tuesday',   start: '14:00', end: '18:00' }],
        d02: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '09:00', end: '13:00' }],
        d03: [{ day: 'Sunday',    start: '08:00', end: '12:00' }, { day: 'Thursday',  start: '14:00', end: '18:00' }],
        d04: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d05: [{ day: 'Tuesday',   start: '08:00', end: '12:00' }, { day: 'Thursday',  start: '13:00', end: '17:00' }],
        d06: [{ day: 'Wednesday', start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d07: [{ day: 'Sunday',    start: '08:00', end: '12:00' }, { day: 'Thursday',  start: '13:00', end: '17:00' }],
        d08: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Wednesday', start: '14:00', end: '18:00' }],
        d09: [{ day: 'Tuesday',   start: '10:00', end: '14:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d10: [{ day: 'Sunday',    start: '13:00', end: '17:00' }, { day: 'Wednesday', start: '09:00', end: '13:00' }],
        d11: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Tuesday',   start: '09:00', end: '12:00' }],
        d12: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Thursday',  start: '10:00', end: '14:00' }],
        d13: [{ day: 'Monday',    start: '14:00', end: '18:00' }, { day: 'Wednesday', start: '14:00', end: '18:00' }],
        d14: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d15: [{ day: 'Sunday',    start: '08:00', end: '16:00' }, { day: 'Wednesday', start: '08:00', end: '16:00' }],
        d16: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d17: [{ day: 'Tuesday',   start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d18: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Thursday',  start: '10:00', end: '14:00' }],
        d19: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Tuesday',   start: '09:00', end: '13:00' }],
        d20: [{ day: 'Wednesday', start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d21: [{ day: 'Monday',    start: '14:00', end: '18:00' }, { day: 'Thursday',  start: '14:00', end: '18:00' }],
        d22: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '10:00', end: '13:00' }],
        d23: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d24: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d25: [{ day: 'Tuesday',   start: '14:00', end: '18:00' }, { day: 'Friday',    start: '10:00', end: '13:00' }],
        d26: [{ day: 'Sunday',    start: '07:00', end: '15:00' }, { day: 'Wednesday', start: '07:00', end: '15:00' }],
        d27: [{ day: 'Monday',    start: '07:00', end: '15:00' }, { day: 'Thursday',  start: '07:00', end: '15:00' }],
        d28: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Tuesday',   start: '10:00', end: '14:00' }],
        d29: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Wednesday', start: '09:00', end: '13:00' }],
        d30: [{ day: 'Tuesday',   start: '11:00', end: '15:00' }, { day: 'Thursday',  start: '11:00', end: '15:00' }],
        d31: [{ day: 'Sunday',    start: '14:00', end: '18:00' }, { day: 'Wednesday', start: '14:00', end: '18:00' }],
        d32: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d33: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Friday',    start: '09:00', end: '12:00' }],
        d34: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d35: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d36: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Tuesday',   start: '10:00', end: '14:00' }],
        d37: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d38: [{ day: 'Wednesday', start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d39: [{ day: 'Tuesday',   start: '11:00', end: '15:00' }, { day: 'Thursday',  start: '11:00', end: '15:00' }],
        d40: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Wednesday', start: '09:00', end: '13:00' }],
        d41: [{ day: 'Monday',    start: '14:00', end: '18:00' }, { day: 'Saturday',  start: '14:00', end: '18:00' }],
        d42: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Tuesday',   start: '14:00', end: '18:00' }],
        d43: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Thursday',  start: '10:00', end: '14:00' }],
        d44: [{ day: 'Wednesday', start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d45: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d46: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d47: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d48: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Wednesday', start: '09:00', end: '13:00' }],
        d49: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Thursday',  start: '10:00', end: '14:00' }],
        d50: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Friday',    start: '09:00', end: '12:00' }],
        d51: [{ day: 'Wednesday', start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d52: [{ day: 'Sunday',    start: '08:00', end: '12:00' }, { day: 'Thursday',  start: '08:00', end: '12:00' }],
        d53: [{ day: 'Monday',    start: '14:00', end: '18:00' }, { day: 'Wednesday', start: '14:00', end: '18:00' }],
        d54: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d55: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d56: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d57: [{ day: 'Sunday',    start: '08:00', end: '16:00' }, { day: 'Wednesday', start: '08:00', end: '16:00' }],
        d58: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d59: [{ day: 'Tuesday',   start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d60: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Tuesday',   start: '10:00', end: '14:00' }],
        d61: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d62: [{ day: 'Wednesday', start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d63: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Tuesday',   start: '09:00', end: '13:00' }],
        d64: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d65: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d66: [{ day: 'Sunday',    start: '14:00', end: '18:00' }, { day: 'Wednesday', start: '14:00', end: '18:00' }],
        d67: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d68: [{ day: 'Tuesday',   start: '10:00', end: '14:00' }, { day: 'Saturday',  start: '10:00', end: '14:00' }],
        d69: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d70: [{ day: 'Monday',    start: '14:00', end: '18:00' }, { day: 'Thursday',  start: '14:00', end: '18:00' }],
        d71: [{ day: 'Sunday',    start: '00:00', end: '23:59' }, { day: 'Monday',    start: '00:00', end: '23:59' }],
        d72: [{ day: 'Wednesday', start: '00:00', end: '23:59' }, { day: 'Thursday',  start: '00:00', end: '23:59' }],
        d73: [{ day: 'Sunday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d74: [{ day: 'Monday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d75: [{ day: 'Tuesday',   start: '08:00', end: '12:00' }, { day: 'Thursday',  start: '14:00', end: '18:00' }],
        d76: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d77: [{ day: 'Monday',    start: '09:00', end: '13:00' }, { day: 'Thursday',  start: '09:00', end: '13:00' }],
        d78: [{ day: 'Tuesday',   start: '09:00', end: '13:00' }, { day: 'Saturday',  start: '09:00', end: '13:00' }],
        d79: [{ day: 'Sunday',    start: '10:00', end: '14:00' }, { day: 'Wednesday', start: '10:00', end: '14:00' }],
        d80: [{ day: 'Monday',    start: '17:00', end: '21:00' }, { day: 'Thursday',  start: '17:00', end: '21:00' }]
      });
    }
  })();

  /* ============================================================
     PUBLIC API
  ============================================================ */
  window.STORE = {

    /* ---- AUTH ---- */
    login: function (role, id, pass) {
      var users = getUsers();
      for (var i = 0; i < users.length; i++) {
        var u = users[i];
        if (u.id === String(id) && u.password === String(pass) && u.role === role) {
          save(K.SESSION, { id: u.id, name: u.name, role: u.role, case_number: u.case_number || null });
          return { success: true };
        }
      }
      return { success: false, error: 'Invalid ID or Password' };
    },

    signup: function (role, name, id, pass) {
      var users = getUsers();
      for (var i = 0; i < users.length; i++) {
        if (users[i].id === String(id)) return { success: false, error: 'ID already registered' };
      }
      var u = { id: String(id), name: name, role: role, password: pass };
      if (role === 'patient') u.case_number = 'CASE-' + String(id);
      users.push(u);
      saveUsers(users);
      return { success: true };
    },

    logout: function () { localStorage.removeItem(K.SESSION); },

    me: function () { return load(K.SESSION); },

    /* Face login: set session by patient name (called after server recognizes face) */
    loginByName: function (name) {
      var users = getUsers();
      for (var i = 0; i < users.length; i++) {
        if (users[i].name === name && users[i].role === 'patient') {
          save(K.SESSION, { id: users[i].id, name: users[i].name, role: 'patient',
                            case_number: users[i].case_number || null });
          return { success: true };
        }
      }
      return { success: false };
    },

    /* ---- APPOINTMENTS ---- */
    book: function (doctorName, date, time) {
      var me = load(K.SESSION);
      if (!me) return { success: false, error: 'Please sign in to book an appointment.' };
      var appts = load(K.APPOINTMENTS) || [];
      appts.push({ patientId: me.id, patient: me.name, doctor: doctorName, date: date, time: time });
      save(K.APPOINTMENTS, appts);
      return { success: true };
    },

    myAppointments: function () {
      var me = load(K.SESSION);
      if (!me) return { success: false, error: 'Not logged in' };
      var appts = load(K.APPOINTMENTS) || [];
      var mine = [];
      for (var i = 0; i < appts.length; i++) {
        if (appts[i].patientId === me.id) mine.push(appts[i]);
      }
      return { success: true, appointments: mine };
    },

    allAppointments: function () {
      return { success: true, appointments: load(K.APPOINTMENTS) || [] };
    },

    /* ---- DOCTORS ---- */
    getDoctors: function () {
      return { success: true, doctors: load(K.DOCTORS) || [] };
    },

    addDoctor: function (name, dept, room) {
      var docs = load(K.DOCTORS) || [];
      docs.push({ id: 'd' + Date.now(), name: name, department: dept, room: room });
      save(K.DOCTORS, docs);
      return { success: true };
    },

    removeDoctor: function (id) {
      var docs = load(K.DOCTORS) || [];
      var out = [];
      for (var i = 0; i < docs.length; i++) {
        if (docs[i].id !== id) out.push(docs[i]);
      }
      save(K.DOCTORS, out);
      var scheds = load(K.SCHEDULES) || {};
      delete scheds[id];
      save(K.SCHEDULES, scheds);
      return { success: true };
    },

    /* ---- SCHEDULES ---- */
    getSchedule: function (docId) {
      var scheds = load(K.SCHEDULES) || {};
      return { success: true, schedule: scheds[docId] || [] };
    },

    setSchedule: function (docId, rows) {
      var scheds = load(K.SCHEDULES) || {};
      scheds[docId] = rows;
      save(K.SCHEDULES, scheds);
      return { success: true };
    },

    /* ---- PATIENTS ---- */
    getPatients: function () {
      var users = getUsers();
      var appts = load(K.APPOINTMENTS) || [];
      var map = {};
      for (var i = 0; i < users.length; i++) {
        if (users[i].role === 'patient') {
          map[users[i].id] = { id: users[i].id, name: users[i].name, case_number: users[i].case_number };
        }
      }
      for (var j = 0; j < appts.length; j++) {
        if (!map[appts[j].patientId]) {
          map[appts[j].patientId] = { id: appts[j].patientId, name: appts[j].patient };
        }
      }
      var list = [];
      for (var k in map) { if (map.hasOwnProperty(k)) list.push(map[k]); }
      return { success: true, patients: list };
    },

    /* ---- EMERGENCIES ---- */
    addEmergency: function (message) {
      var me = load(K.SESSION);
      var em = load(K.EMERGENCIES) || [];
      em.push({
        patient: me ? me.name : 'Unknown',
        message: message || 'Emergency Help Requested',
        time: new Date().toLocaleString()
      });
      save(K.EMERGENCIES, em);
      return { success: true };
    },

    listEmergencies: function () {
      return { success: true, emergencies: load(K.EMERGENCIES) || [] };
    },

    clearEmergencies: function () {
      save(K.EMERGENCIES, []);
      return { success: true };
    },

    /* ---- TRIAGE ---- */
    addTriage: function (data) {
      var me = load(K.SESSION);
      var list = load(K.TRIAGES) || [];
      var levelColors = { 1: 'Red', 2: 'Orange', 3: 'Yellow', 4: 'Green' };
      var levelLabels = { 1: 'IMMEDIATE', 2: 'VERY URGENT', 3: 'URGENT', 4: 'STANDARD' };
      var lvl = data.level || 4;
      list.push({
        id: 'TR-' + Date.now(),
        patient: me ? me.name : 'Guest',
        chiefComplaint: data.chiefComplaint || '',
        painScore: data.painScore || 0,
        symptoms: data.symptoms || [],
        level: lvl,
        label: data.label || levelLabels[lvl],
        color: data.color || levelColors[lvl],
        recommendation: data.recommendation || '',
        time: new Date().toLocaleString()
      });
      save(K.TRIAGES, list);
      return { success: true };
    },

    listTriages: function () {
      return { success: true, triages: load(K.TRIAGES) || [] };
    },

    clearTriages: function () {
      save(K.TRIAGES, []);
      return { success: true };
    }
  };

})();
