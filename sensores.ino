#include "HX711.h"


#define PIN_LDR   A0
#define PIN_NTC   A1
#define PIN_PTC   A2
#define HX711_DT  4
#define HX711_SCK 5
#define PIN_LED_INDICADOR 2

const int   UMBRAL_LDR_OSCURO_ADC = 300;
const float UMBRAL_PTC_CALIENTE_OHM = 2300.0;

const float VCC     = 5.0;
const int   ADC_RES = 1023;

const float R_FIJA_LDR = 10000.0; 
const float R_FIJA_NTC = 10000.0; 
const float R_FIJA_PTC = 2000.0;  

const float NTC_NOMINAL  = 10000.0;
const float NTC_BETA     = 3950.0;
const float TEMP_NOMINAL = 25.0; // °C

HX711 balanza;
bool hx711_ok = false;
float factor_calibracion = 2280.0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F(">>> Iniciando setup..."));

  pinMode(PIN_LED_INDICADOR, OUTPUT);
  digitalWrite(PIN_LED_INDICADOR, LOW);

  Serial.println(F(">>> Verificando HX711 (timeout 2s)..."));
  balanza.begin(HX711_DT, HX711_SCK);

  unsigned long t0 = millis();
  while (millis() - t0 < 2000) {
    if (balanza.is_ready()) {
      hx711_ok = true;
      break;
    }
  }

  if (hx711_ok) {
    balanza.set_scale(factor_calibracion);
    balanza.tare();
    Serial.println(F(">>> HX711 listo"));
  } else {
    Serial.println(F(">>> HX711 NO responde (revisa VCC/GND/DT/SCK). Continuando sin celda de carga."));
  }

  Serial.println(F(">>> Setup completo, entrando al loop()"));
}

void loop() {

  int ldrADC = analogRead(PIN_LDR);
  float ldrV = ldrADC * (VCC / ADC_RES);
  // Config: Vcc - R_FIJA_LDR - nodo(ADC) - LDR - GND
  float rLDR = R_FIJA_LDR * (VCC / ldrV - 1.0);

  int ntcADC = analogRead(PIN_NTC);
  float ntcV = ntcADC * (VCC / ADC_RES);

  float rNTC = R_FIJA_NTC * (ntcV / (VCC - ntcV));
  float tempK = 1.0 / (1.0 / (TEMP_NOMINAL + 273.15) +
                        (1.0 / NTC_BETA) * log(rNTC / NTC_NOMINAL));
  float tempC = tempK - 273.15;


  int ptcADC = analogRead(PIN_PTC);
  float ptcV = ptcADC * (VCC / ADC_RES);
  
  float rPTC = R_FIJA_PTC * (ptcV / (VCC - ptcV));


  float peso = 0.0;
  if (hx711_ok && balanza.is_ready()) {
    peso = balanza.get_units(5); 
  }


  bool oscuro   = (ldrADC < UMBRAL_LDR_OSCURO_ADC);
  bool caliente = (rPTC > UMBRAL_PTC_CALIENTE_OHM);
  bool ledActivo = oscuro || caliente;
  digitalWrite(PIN_LED_INDICADOR, ledActivo ? HIGH : LOW);



  Serial.print(F("LDR  | ADC: ")); Serial.print(ldrADC);
  Serial.print(F(" | V: "));       Serial.print(ldrV, 3);
  Serial.print(F(" | R: "));       Serial.print(rLDR, 1); Serial.println(F(" ohm"));

  Serial.print(F("NTC  | ADC: ")); Serial.print(ntcADC);
  Serial.print(F(" | V: "));       Serial.print(ntcV, 3);
  Serial.print(F(" | Temp: "));    Serial.print(tempC, 2); Serial.println(F(" C"));

  Serial.print(F("PTC  | ADC: ")); Serial.print(ptcADC);
  Serial.print(F(" | V: "));       Serial.print(ptcV, 3);
  Serial.print(F(" | R: "));       Serial.print(rPTC, 1); Serial.println(F(" ohm"));

  Serial.print(F("PESO | "));      Serial.print(peso, 2); Serial.println(F(" g"));

  Serial.print(F("LED  | oscuro: "));  Serial.print(oscuro ? F("SI") : F("NO"));
  Serial.print(F(" | caliente: "));    Serial.print(caliente ? F("SI") : F("NO"));
  Serial.print(F(" | estado: "));      Serial.println(ledActivo ? F("ENCENDIDO") : F("APAGADO"));


  Serial.print(ldrADC);      Serial.print(",");
  Serial.print(ldrV, 3);     Serial.print(",");
  Serial.print(rLDR, 1);     Serial.print(",");
  Serial.print(ntcADC);      Serial.print(",");
  Serial.print(ntcV, 3);     Serial.print(",");
  Serial.print(tempC, 2);    Serial.print(",");
  Serial.print(ptcADC);      Serial.print(",");
  Serial.print(ptcV, 3);     Serial.print(",");
  Serial.print(rPTC, 1);     Serial.print(",");
  Serial.println(peso, 2);

  delay(500);
}
