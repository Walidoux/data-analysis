I. Introduction :

Chers membres du jury bonjour, aujourd’hui on vous présente notre projet réalisé avec Python.
Ce choix est a été pertinent dans le cadre de l’analyse de cette base de donnée pour qu’on puisse
bien traiter toutes les valeurs le plus correct et le précis du possible puisque le langage nous
offre une bonne flexibilité pour manier cette base de donnée, donc autant s’en servir, nous allons
démontrer ça au fur et à mesure. Le temps consacré dépasse largement 150h on l’a commencé depuis
plus d’un mois, beaucoup de choses vont être traitées, on essayera d’être bref.

Nous utilisons pip qui est le package manager de python (outil de gestion des librairies), nous
utilisons (…). On a pris le soin de tout documenter sur un fichier juste ici pour l’installation et
l’utilisation du projet.
On utilise aussi git qui est un système de contrôle de version et qui nous permettre de traquer tout
les fichiers du projet de sorte a ce que le projet soit déployable, grâce à cet outil, sur Github qui
est un service de web d’hébergement de projets qu’on peut partager et où on peut collaborer avec
d’autres développeurs pour écrire du code.
Nous avons utiliser la librairie snakemd pour générer du markdown, c’est un langage de balise qui va
nous permettre de créer et de formater du texte mais essentiellement créer des tableaux.
Parmi un de ces tableaux, on a identifié pour chaque variable qu’on a appelé dictionnaire toutes les
valeurs valides et non valides.

Pour entrer dans le vif du sujet, l’importation se fait de manière standard en lisant fichier .csv
Pour lire les valeurs des variables, nous avons précodifier les entêtes de sorte à ce que par exemple
la variable « Nombre de livres lus par an » soit abrégé sous forme de sigle et donc « NDLLPA » pour
faciliter la lecture, on a fait en sorte de générer une documentation pour avoir un vue d’ensemble
de toutes les variables mais surtout pour s’en rappeler.

Avant de traiter les données, on s’est assurée à ce que toutes les données sensibles soient supprimées
à savoir l’adresse mail et le nom d’utilisateur. Même chose pour les variables qui ne sont pertinentes
pour l’analyse comme l’année d’étude, parce que statistiquement on étudie qu’un seule échantillon qui
est les étudiants de la troisième année, programatiquement, c’est une constante et non pas un jeu de
donnée. Toutes choses égales par ailleurs, l’horodateur à part si on veut estimer le temps de réponse
des étudiants au partage du formulaire, mais on s’est rendu compte qu’il y a trop de biais qui peuvent
fausser la réalité, donc à préférer la supprimer.
Ce qui est intéressant, c’est ce qu’il y a eu un cas, où une variable, a été supprimé sans notre
intervention, qui est l’activité physique, parce que deux conditions ont été satisfaites lorsqu’on
a mobilisé la partie de la gestion des données manquantes dans notre cours. La première condition
précise qu’une variable avec trop de valeurs manquantes peut être supprimée si cette dernière
représente de 30% jusqu’à 40% des données manquantes. La deuxième condition, à caractère générale,
nous fixe un taux qui doit être inférieur à 5% des données invalides de toutes les variables. Et encore
 une fois c’était effectivement le cas pour l’activité physique.

Voilà donc niveau traitement des données, on est partie sur une logique de variable numérique et
catégorielle qu’on a respectivement appelé StoreSet et StoreCollection, qui sont deux classes qui
héritent de la classe DataManager.

Pour la variable catégorique, on traite :
- Des valeurs normalisées puisqu’il s’avère que Fès comme valeur dans la variable ville d’origine n’est
strictement égal à Fes sans accent, du coup on capitalise tout les caractères et on transforme les
caractères unicodes par leurs équivalents.
- Les fautes de frappe pour matcher approximativement les valeurs dupliquées, dans le même exemple
Fès est intuitivement l’équivalent de Fez. On a utilisé Laveinshtein comme algorithme permettant de
mesurer la distance ou la différence entre deux chaînes de caractères. La condition qu’on a établie
pour savoir si deux mots sont les mêmes se traduit en vérifiant si la distance calculée est inférieure
ou égale à un seuil qu’on a fixé à 2, si ca dépasse ce seuil, cela veut dire que les mots ne se
ressemblent pas, dans le cas contraire, ils sont identiques. On a effectué plusieurs tests et c’est
le meilleure seuil avec lequel on peut assurer mesurer la distance entre deux mots.
- Les valeurs invalides qui sont représentées typologiquement sous forme d’une énumération pour
qu’on puisse les corriger après. On vérifie d’abord si elles nulles ou inconnues, sinon on vérifie
via du REGEX, connues sous le nom des expressions régulières, que la valeur est belle est bien
alphanumérique et qu’elle ne possède pas de caractère qui nie à la lecture simple d’une chaîne de
caractère.
- Des cas spécifiques ou certaines variables ont des valeurs comme « AUCUN », « PAS » « NON » qui
sous entend une seule valeur, du coup on regroupe toutes les vraisemblances, et encore d’autres
scénarios notamment ou l’année du baccalauréat possède des valeurs avec des séparateurs ou on a
juste pris la première partie, encore ou on devait classifier la branche choisie au bac de sorte
à ce que l’option SVT fait référence à la branche « science expérimentale » et que « SGC - science
gestion comptable » fait référence à la branche économique, et encore dans la même logique des
classifications des données pour les logiciels les plus utilisées.
- Récursivement une valeur qui peut avoir de 2 jusqu’à 4 valeurs, séparées soit par des points virgules,
par des virgules, par des slashs ou soit sinon par « ET »

Ça d’un côté, de l’autre côté des variables numériques ou on traite :
- Les valeurs invalides de la même manière que de ce qui a précédé.
- Le cas d’un entier exprimé en chaîne de caractère en vérifiant si la valeur est une instance de la
classe str, puis on extrait la partie entier naturel à l’aide des expressions régulières ou on vérifie
si il y a une séquence de chiffres.

En revenant toujours à la partie du traitement des données manquantes, on a utilisé quatre méthodes
pour substituer ces valeurs.
- La médiane a été utilisée sur les variables numériques si et uniquement si il y a des valeurs aberrantes. La raison est simple, on a trouvé qu’elle n’est pas sensible aux outliers, et donc aux valeurs aberrantes et qu’elle représente des estimations plus précises.
- La moyenne en arrondissant à la virgule près pour les variables numériques surtout au niveau de la
variable « dépenses mensuelles ».
- Le mode sur la base des valeurs connues d’une variable catégorique qui incrémente la fréquence de
la valeur la plus fréquente.
- La régression linéaire ou on cherche à trouver une variable indépendante Y qui (…)




Le seul inconv utilise une carte prédéfinie avec une résolution grossière,
ce qui a tendance à ommettre les très petits pays insulaires, surtout les îles proches de l’équateur
comme São Tomé-et-Principe. C'est une limite de rendu cartographique dans Plotly.
