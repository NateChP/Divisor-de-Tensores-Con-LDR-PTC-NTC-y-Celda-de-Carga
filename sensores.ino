
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

HX711 balanza;
bool hx711_ok = false;
float factor_calibracion = 103726289.0; 

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F(">>> Iniciando setup..."));

  pinMode(PIN_LED_INDICADOR, OUTPUT);
  digitalWrite(PIN_LED_INDICADOR, LOW);

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
    Serial.println(F(">>> HX711 NO responde. Continuando sin celda de carga."));
  }

  Serial.println(F(">>> Setup completo, entrando al loop()"));
}

void loop() {
  int ldrADC = analogRead(PIN_LDR);
  float ldrV = ldrADC * (VCC / ADC_RES);
  float rLDR = (ldrV > 0 && (VCC - ldrV) > 0) ? R_FIJA_LDR * (VCC / ldrV - 1.0) : 0.0;

  int ntcADC = analogRead(PIN_NTC);
  float ntcV = ntcADC * (VCC / ADC_RES);
  float rNTC = (VCC - ntcV > 0) ? R_FIJA_NTC * (ntcV / (VCC - ntcV)) : 0.0;

  int ptcADC = analogRead(PIN_PTC);
  float ptcV = ptcADC * (VCC / ADC_RES);
  float rPTC = (VCC - ptcV > 0) ? R_FIJA_PTC * (ptcV / (VCC - ptcV)) : 0.0;

  float peso = 0.0;
  if (hx711_ok && balanza.is_ready()) {
    peso = balanza.get_units(5) * 100.0; 
  }

  bool oscuro   = (ldrADC < UMBRAL_LDR_OSCURO_ADC);
  bool caliente = (rPTC > UMBRAL_PTC_CALIENTE_OHM);
  bool ledActivo = oscuro || caliente;
  digitalWrite(PIN_LED_INDICADOR, ledActivo ? HIGH : LOW);

  Serial.print(ldrV, 3);     Serial.print(",");
  Serial.print(rLDR, 1);     Serial.print(",");
  Serial.print(rNTC, 1);     Serial.print(",");
  Serial.print(ptcV, 3);     Serial.print(",");
  Serial.print(rPTC, 1);     Serial.print(",");
  Serial.print(peso, 2);     Serial.print(",");
  Serial.println(ledActivo ? 1 : 0);

  delay(2000);
}
