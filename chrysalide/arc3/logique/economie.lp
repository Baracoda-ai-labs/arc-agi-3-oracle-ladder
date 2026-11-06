% SPDX-License-Identifier: MIT-0
% F (charte 21-30, CW-369/370) : ÉCONOMIE pour le noyau ASP qui joue (axiome A-U5, forme corrigée par B,
% docs/ONTOLOGIE_FORMELLE_GDL_VGDL.md). À inclure avec l'encodage de C/G, qui fournit `time/1`, `does/2` et `gagne/1`.
% Paramètres de l'étage 2 (fiche du jeu, ou lus par le moteur : `economie_plan.faits_asp`) :
%   reserve0(R).        réserve au début du plan (economie_plan.reserve_niveau, marge déduite)
%   cout(A, C).         barème : coût de l'action A (absent → 1 ; 0 = gratuite)
%   seuil(S).           défaite quand la réserve tombe à S ou moins (absent → 0)
%   recharge(N, T).     effet explicite : +N à la réserve après le coup T (fourni par les lois du jeu)
%   epuisement_d_abord. option du jeu (ontologie v1.2 de B, `ordre_victoire_epuisement`, victoire d'abord vérifiée
%                       dans 9/20 jeux seulement) : l'épuisement est testé AVANT la victoire ; absent → la victoire prime
% Règles :
%   - la réserve est un FLUENT (jamais le budget humain, qui est une métadonnée d'évaluation) ;
%   - VICTOIRE AVANT DÉFAITE par défaut : un état gagnant n'est pas perdu (coup gagnant gratuit), sauf option contraire ;
%   - un plan ne passe jamais par un état perdu.

seuil_j(S) :- seuil(S).
seuil_j(0) :- not seuil(_).
cout_j(A, C) :- does(A, _), cout(A, C).
cout_j(A, 1) :- does(A, _), not cout(A, _).

reserve(R, 0) :- reserve0(R).
reserve(R - C + K, T + 1) :- reserve(R, T), does(A, T), cout_j(A, C), time(T + 1),
                             K = #sum { N : recharge(N, T) }.
perdu(T) :- reserve(R, T), seuil_j(S), R <= S, not gagne(T), T > 0.
perdu(T) :- reserve(R, T), seuil_j(S), R <= S, epuisement_d_abord, T > 0.
:- perdu(T).
