package dev.yai.app.core

import java.math.BigDecimal
import java.math.MathContext
import java.math.RoundingMode
import kotlin.math.pow

/** Güvenli hesap makinesi: + - * / ^ % ( ) ve sqrt, sin, cos, tan, log, ln, abs, round, pi, e. "%" sondaysa yüzde. */
object Calc {
    fun eval(input: String): Double {
        val s = input.lowercase().replace("×", "*").replace("÷", "/").replace(",", ".").replace("−", "-").replace(" ", "")
        val p = Parser(s)
        val v = p.expr()
        if (p.i != s.length) throw IllegalArgumentException("Anlaşılmayan ifade: '${s.substring(p.i)}'")
        return v
    }

    fun format(v: Double): String {
        if (v.isNaN() || v.isInfinite()) return v.toString()
        val bd = BigDecimal(v).round(MathContext(12, RoundingMode.HALF_UP)).stripTrailingZeros()
        return if (bd.scale() < 0) bd.setScale(0).toPlainString() else bd.toPlainString()
    }

    private class Parser(val s: String) {
        var i = 0
        private fun peek() = if (i < s.length) s[i] else '\u0000'
        private fun eat(c: Char): Boolean { if (peek() == c) { i++; return true }; return false }

        fun expr(): Double {
            var v = term()
            while (true) v = when { eat('+') -> v + term(); eat('-') -> v - term(); else -> return v }
        }

        private fun term(): Double {
            var v = factor()
            while (true) v = when {
                eat('*') -> v * factor()
                eat('/') -> { val d = factor(); if (d == 0.0) throw ArithmeticException("Sıfıra bölme"); v / d }
                eat('%') -> if (peek().isDigit() || peek() == '(') v % factor() else v / 100.0
                else -> return v
            }
        }

        private fun factor(): Double {
            val base = unary()
            return if (eat('^')) base.pow(factor()) else base
        }

        private fun unary(): Double = when {
            eat('-') -> -unary()
            eat('+') -> unary()
            else -> primary()
        }

        private fun primary(): Double {
            if (eat('(')) { val v = expr(); if (!eat(')')) throw IllegalArgumentException("Parantez kapanmadı"); return v }
            val start = i
            if (peek().isDigit() || peek() == '.') {
                while (peek().isDigit() || peek() == '.') i++
                return s.substring(start, i).toDouble()
            }
            while (peek().isLetter()) i++
            val name = s.substring(start, i)
            when (name) { "pi", "π" -> return Math.PI; "e" -> return Math.E }
            if (name.isEmpty()) throw IllegalArgumentException("Sayı bekleniyordu")
            if (!eat('(')) throw IllegalArgumentException("'$name(' bekleniyordu")
            val a = expr(); if (!eat(')')) throw IllegalArgumentException("Parantez kapanmadı")
            return when (name) {
                "sqrt", "karekok", "kok" -> kotlin.math.sqrt(a); "sin" -> kotlin.math.sin(Math.toRadians(a))
                "cos" -> kotlin.math.cos(Math.toRadians(a)); "tan" -> kotlin.math.tan(Math.toRadians(a))
                "log" -> kotlin.math.log10(a); "ln" -> kotlin.math.ln(a); "abs" -> kotlin.math.abs(a)
                "round", "yuvarla" -> kotlin.math.round(a); else -> throw IllegalArgumentException("Bilinmeyen fonksiyon: $name")
            }
        }
    }
}
