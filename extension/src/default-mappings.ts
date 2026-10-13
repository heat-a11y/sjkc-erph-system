// Default field mappings for Malaysian MOE portals
// These are pre-configured selectors for common MOE web forms.
// Teachers can add/remove/edit these in the extension's Options page.

import type { FieldMapping } from "../../shared/types";

export const DEFAULT_MAPPINGS: FieldMapping[] = [
  // --- IDMe (idme.moe.gov.my) — teacher profile update ---
  { id: "dm-idme-name", host: "idme.moe.gov.my", fieldId: "nama_lengkap", selector: "input#nama_penuh, input[name=nama_penuh], input#full_name, input[name=full_name]", source: "identity", sourceKey: "name" },
  { id: "dm-idme-ic", host: "idme.moe.gov.my", fieldId: "no_ic", selector: "input#no_ic, input[name=no_ic], input#ic_number, input[name=ic_number]", source: "identity", sourceKey: "ic" },
  { id: "dm-idme-email", host: "idme.moe.gov.my", fieldId: "emel", selector: "input#email, input[name=email], input#emel", source: "identity", sourceKey: "email" },
  { id: "dm-idme-phone", host: "idme.moe.gov.my", fieldId: "telefon", selector: "input#phone, input[name=phone], input#telefon, input[name=telefon]", source: "identity", sourceKey: "phone" },
  { id: "dm-idme-dob", host: "idme.moe.gov.my", fieldId: "tarikh_lahir", selector: "input#dob, input[name=dob], input#tarikh_lahir", source: "identity", sourceKey: "ic", transform: "ic2dob" },

  // --- IDMe: Teacher-specific fields ---
  { id: "dm-idme-dept", host: "idme.moe.gov.my", fieldId: "bahagian", selector: "input#bahagian, input[name=bahagian], select#bahagian", source: "identity", sourceKey: "department" },
  { id: "dm-idme-pos", host: "idme.moe.gov.my", fieldId: "jawatan", selector: "input#jawatan, input[name=jawatan], select#jawatan", source: "identity", sourceKey: "position" },
  { id: "dm-idme-school", host: "idme.moe.gov.my", fieldId: "kod_sekolah", selector: "input#kod_sekolah, input[name=kod_sekolah], select#kod_sekolah", source: "identity", sourceKey: "schoolCode" },

  // --- SGMy (sgmy.moe.gov.my) — teacher certificate ---
  { id: "dm-sgmy-ic", host: "sgmy.moe.gov.my", fieldId: "ic", selector: "input#ic_no, input[name=ic_no], input#nric, input[name=nric]", source: "identity", sourceKey: "ic" },
  { id: "dm-sgmy-name", host: "sgmy.moe.gov.my", fieldId: "name", selector: "input#nama, input[name=nama], input#name, input[name=name]", source: "identity", sourceKey: "name", transform: "upper" },

  // --- MySST (mysst.moe.gov.my) — SST (Student Specific Target) ---
  { id: "dm-mysst-teacher", host: "mysst.moe.gov.my", fieldId: "guru", selector: "input#guru_id, input[name=guru_id], select#guru_id", source: "identity", sourceKey: "teacherId" },
  { id: "dm-mysst-school", host: "mysst.moe.gov.my", fieldId: "sekolah", selector: "input#kod_sekolah, input[name=kod_sekolah], select#kod_sekolah", source: "identity", sourceKey: "schoolCode" },

  // --- APDM (apdmkpm.moe.gov.my) — student database ---
  { id: "dm-apdm-school", host: "apdmkpm.moe.gov.my", fieldId: "kod_sekolah", selector: "input#kod_sekolah, input[name=kod_sekolah], select#kod_sekolah", source: "identity", sourceKey: "schoolCode" },
  { id: "dm-apdm-teacher", host: "apdmkpm.moe.gov.my", fieldId: "guru", selector: "input#guru_id, input[name=guru_id], select#guru_id", source: "identity", sourceKey: "teacherId" },

  // --- Generic fallback for *.moe.gov.my ---
  { id: "dm-generic-name", host: "moe.gov.my", fieldId: "nama", selector: "input[name*nama], input#nama, input[name=name]", source: "identity", sourceKey: "name" },
  { id: "dm-generic-ic", host: "moe.gov.my", fieldId: "ic", selector: "input[name*nric], input[name*nokp], input#ic, input[name=ic]", source: "identity", sourceKey: "ic" },
];
