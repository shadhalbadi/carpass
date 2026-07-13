/** Popular Gulf / import makes and models for searchable dropdowns. */

export const CAR_MAKES_MODELS: Record<string, string[]> = {
  Toyota: [
    "Camry",
    "Corolla",
    "Land Cruiser",
    "Prado",
    "Hilux",
    "RAV4",
    "Fortuner",
    "Yaris",
    "Avalon",
    "Highlander",
    "4Runner",
    "Sequoia",
    "Tundra",
    "Tacoma",
    "Crown",
    "C-HR",
  ],
  Lexus: ["LX", "LX 570", "LX 600", "GX", "GX 460", "RX", "ES", "IS", "NX", "UX", "LS"],
  Nissan: ["Patrol", "Altima", "Maxima", "X-Trail", "Pathfinder", "Sunny", "Kicks", "Navara", "Armada", "Sentra", "Rogue"],
  Honda: ["Accord", "Civic", "CR-V", "Pilot", "HR-V", "City", "Odyssey", "Passport"],
  Hyundai: ["Tucson", "Santa Fe", "Elantra", "Sonata", "Creta", "Palisade", "Accent", "Kona", "Venue"],
  Kia: ["Sportage", "Sorento", "Optima", "Cerato", "Telluride", "Seltos", "Carnival", "Rio", "K5"],
  Mitsubishi: ["Pajero", "L200", "Outlander", "ASX", "Montero", "Eclipse Cross", "Attrage"],
  Ford: ["F-150", "Explorer", "Edge", "Mustang", "Escape", "Ranger", "Expedition", "Bronco", "Fusion"],
  Chevrolet: ["Tahoe", "Suburban", "Silverado", "Malibu", "Traverse", "Equinox", "Camaro", "Captiva"],
  GMC: ["Yukon", "Sierra", "Terrain", "Acadia", "Canyon"],
  BMW: ["X5", "X3", "X6", "X7", "3 Series", "5 Series", "7 Series", "X1", "X4"],
  Mercedes: [
    "C-Class",
    "E-Class",
    "S-Class",
    "GLE",
    "GLC",
    "GLS",
    "G-Class",
    "A-Class",
    "CLA",
  ],
  "Land Rover": ["Range Rover", "Range Rover Sport", "Discovery", "Defender", "Evoque", "Velar"],
  Jeep: ["Grand Cherokee", "Wrangler", "Cherokee", "Compass", "Renegade", "Gladiator"],
  Audi: ["A4", "A6", "A8", "Q5", "Q7", "Q8", "Q3", "A3", "e-tron"],
  Volkswagen: ["Tiguan", "Golf", "Passat", "Touareg", "Jetta", "Teramont", "Atlas"],
  Mazda: ["CX-5", "CX-9", "CX-30", "Mazda3", "Mazda6", "CX-3"],
  Subaru: ["Outback", "Forester", "Crosstrek", "Impreza", "Ascent", "Legacy"],
  Porsche: ["Cayenne", "Macan", "Panamera", "911", "Taycan"],
  Volvo: ["XC90", "XC60", "XC40", "S90", "S60"],
  Infiniti: ["QX80", "QX60", "QX50", "Q50", "Q60"],
  Cadillac: ["Escalade", "XT5", "XT6", "CT5", "CT4"],
  Dodge: ["Charger", "Challenger", "Durango", "Ram"],
  Ram: ["1500", "2500", "3500"],
  Suzuki: ["Swift", "Vitara", "Jimny", "Ertiga", "Dzire"],
  Isuzu: ["D-Max", "MU-X"],
  Peugeot: ["3008", "5008", "208", "2008", "508"],
  Renault: ["Duster", "Megane", "Captur", "Koleos", "Symbol"],
  Geely: ["Coolray", "Okavango", "Tugella", "Emgrand"],
  Changan: ["CS75", "CS35", "Alsvin", "UNI-T", "Hunter"],
  MG: ["ZS", "HS", "RX5", "5", "GT"],
  Tesla: ["Model 3", "Model Y", "Model S", "Model X"],
  Genesis: ["G70", "G80", "GV70", "GV80"],
  Acura: ["MDX", "RDX", "TLX", "Integra"],
  Lincoln: ["Navigator", "Aviator", "Nautilus", "Corsair"],
};

export const CAR_MAKES = Object.keys(CAR_MAKES_MODELS).sort((a, b) => a.localeCompare(b));

export function modelsForMake(make: string): string[] {
  if (!make.trim()) return [];
  const key = CAR_MAKES.find((m) => m.toLowerCase() === make.trim().toLowerCase());
  return key ? [...CAR_MAKES_MODELS[key]] : [];
}

export function yearOptions(from = 1990, to = new Date().getFullYear() + 1): string[] {
  const years: string[] = [];
  for (let y = to; y >= from; y -= 1) years.push(String(y));
  return years;
}
