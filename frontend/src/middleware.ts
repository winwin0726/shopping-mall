// middleware??Next.js 16?љВёю deprecated??// Ж░юв░ю ?еЖ│ё?љВёю??в╣ёьЎю?▒ьЎћ ?????їВЮ╝?ђ ??аю?┤вЈё вг┤в░Е
// ?ёвАю?ЋВЁў ??"proxy" в░ЕВІЮ?╝вАю ?гЖхг???ѕВаЋ

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // вфевЊа ?ћВ▓Г ЖиИвЃЦ ?хЖ│╝ (Ж░юв░ю вфевЊю)
  return NextResponse.next();
}

// ?ёвг┤ Ж▓йвАю?љвЈё вДцВ╣Г?ўВ? ?івЈёвА?в╣?в░░ВЌ┤ ?цВаЋ
export const config = {
  matcher: [],
};
